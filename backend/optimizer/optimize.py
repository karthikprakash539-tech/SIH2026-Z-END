"""
BlockSync Optimization Engine (Google OR-Tools CP-SAT).

Place at: backend/optimizer/optimize.py
Run from inside backend/optimizer/:

    python optimize.py

What it does, in order:
1. Loads real Defects from the DB. For each one without a BlockRequest
   yet, predicts duration (Model 1) and delay impact (Model 2), computes
   an explainable priority score, and creates a BlockRequest row.
2. Builds a CP-SAT model: each request gets a day (0-6, one week) and a
   start hour within the nightly maintenance window (00:00-06:00).
   Hard constraints: no two requests on the same section overlap, and
   no two requests in the same department overlap (single-crew
   assumption per department, stated explicitly for the demo).
3. Solves the SAME model with three different objective weightings to
   produce Plan A (minimize delay), Plan B (maximize maintenance
   completed), Plan C (balanced) -- this is genuine re-optimization,
   not three copies of one result.
4. Saves each plan + its schedule items to the database and prints a
   comparison table.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "models"))

from models import engine, Section, Defect, BlockRequest, PlanCandidate, ScheduleItem
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from joblib import load
from ortools.sat.python import cp_model
import pandas as pd

Session = sessionmaker(bind=engine)
session = Session()

ML_DIR = os.path.join(os.path.dirname(__file__), "..", "ml")
duration_bundle = load(os.path.join(ML_DIR, "duration_model.pkl"))
delay_bundle = load(os.path.join(ML_DIR, "delay_model.pkl"))

MAINTENANCE_WINDOW_HOURS = 6   # 00:00-06:00 nightly window
PLANNING_DAYS = 7              # weekly plan
WEEK_START = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


# ---------------------------------------------------------------------------
# STEP 1: Ensure every open defect has a BlockRequest with ML predictions
# ---------------------------------------------------------------------------

def predict_duration(department, severity, overdue_days):
    model = duration_bundle["model"]
    cols = duration_bundle["feature_cols"]
    row = {c: 0 for c in cols}
    row["severity"] = severity
    row["overdue_days"] = overdue_days
    dept_col = f"department_{department}"
    if dept_col in row:
        row[dept_col] = 1
    X = pd.DataFrame([row])[cols]
    pred = float(model.predict(X)[0])
    return max(0.5, min(pred, MAINTENANCE_WINDOW_HOURS))  # clip to fit the nightly window


def predict_delay(block_duration_hours, traffic_density, time_of_day_peak=0):
    model = delay_bundle["model"]
    cols = delay_bundle["feature_cols"]
    X = pd.DataFrame([{
        "block_duration_hours": block_duration_hours,
        "traffic_density": traffic_density,
        "time_of_day_peak": time_of_day_peak,
    }])[cols]
    return max(0.0, float(model.predict(X)[0]))


def compute_priority(severity, overdue_days, traffic_density):
    """Explainable weighted formula -- deliberately NOT ML, so it stays
    defensible under questioning."""
    return round(severity * 15 + overdue_days * 1.5 + traffic_density * 10, 1)


def ensure_block_requests():
    open_defects = session.query(Defect).filter(Defect.status == "Open").all()
    created = 0
    for d in open_defects:
        existing = session.query(BlockRequest).filter(BlockRequest.defect_id == d.id).first()
        if existing:
            continue

        section = session.query(Section).filter(Section.id == d.section_id).first()
        duration = predict_duration(d.department, d.severity, d.overdue_days)
        delay = predict_delay(duration, section.traffic_density)
        priority = compute_priority(d.severity, d.overdue_days, section.traffic_density)

        req = BlockRequest(
            department=d.department,
            section_id=d.section_id,
            defect_id=d.id,
            requested_start=WEEK_START,   # placeholder -- optimizer assigns the real slot
            requested_end=WEEK_START + timedelta(hours=duration),
            priority_score=priority,
            predicted_duration_hours=round(duration, 2),
            predicted_delay_minutes=round(delay, 1),
            status="Pending",
        )
        session.add(req)
        created += 1
    session.commit()
    print(f"[ok] {created} new block requests created from open defects "
          f"(with ML-predicted duration + delay + priority score)")


# ---------------------------------------------------------------------------
# STEP 2: Build and solve the CP-SAT model for one weighting profile
# ---------------------------------------------------------------------------

def solve_plan(requests, w_priority, w_delay, plan_label, strategy):
    model = cp_model.CpModel()
    horizon = PLANNING_DAYS * MAINTENANCE_WINDOW_HOURS  # compressed timeline: 7*6 = 42 "night hours"

    presence = {}
    day = {}
    start_in_day = {}
    global_start = {}
    global_end = {}
    intervals = {}

    for r in requests:
        dur = max(1, round(r.predicted_duration_hours or 2))
        dur = min(dur, MAINTENANCE_WINDOW_HOURS)
        rid = r.id

        presence[rid] = model.NewBoolVar(f"presence_{rid}")
        day[rid] = model.NewIntVar(0, PLANNING_DAYS - 1, f"day_{rid}")
        start_in_day[rid] = model.NewIntVar(0, MAINTENANCE_WINDOW_HOURS - dur, f"start_{rid}")

        global_start[rid] = model.NewIntVar(0, horizon, f"gstart_{rid}")
        global_end[rid] = model.NewIntVar(0, horizon, f"gend_{rid}")
        model.Add(global_start[rid] == day[rid] * MAINTENANCE_WINDOW_HOURS + start_in_day[rid])
        model.Add(global_end[rid] == global_start[rid] + dur)

        intervals[rid] = model.NewOptionalIntervalVar(
            global_start[rid], dur, global_end[rid], presence[rid], f"interval_{rid}"
        )

    # Hard constraint: no two requests on the same SECTION overlap
    sections = {r.section_id for r in requests}
    for sec_id in sections:
        sec_intervals = [intervals[r.id] for r in requests if r.section_id == sec_id]
        if len(sec_intervals) > 1:
            model.AddNoOverlap(sec_intervals)

    # Hard constraint: no two requests in the same DEPARTMENT overlap
    # (single-crew-per-department assumption, stated explicitly for this prototype)
    departments = {r.department for r in requests}
    for dept in departments:
        dept_intervals = [intervals[r.id] for r in requests if r.department == dept]
        if len(dept_intervals) > 1:
            model.AddNoOverlap(dept_intervals)

    # Objective: weighted combination of priority addressed vs delay caused
    # scaled to integers (CP-SAT requires integer coefficients).
    # Delay is divided by DELAY_SCALE before weighting -- without this,
    # real-world delay values (which can run 100+ minutes) dominate the
    # priority score (roughly 40-150 points) even at modest weights,
    # causing the solver to correctly-but-uselessly schedule nothing.
    DELAY_SCALE = 20
    terms = []
    for r in requests:
        rid = r.id
        priority_term = int((r.priority_score or 0) * w_priority)
        delay_term = int(((r.predicted_delay_minutes or 0) / DELAY_SCALE) * w_delay)
        terms.append(presence[rid] * (priority_term - delay_term))
    model.Maximize(sum(terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"[warn] {plan_label}: solver found no feasible solution")
        return None

    # collect results
    scheduled = []
    total_delay = 0.0
    total_priority_addressed = 0.0
    for r in requests:
        rid = r.id
        if solver.Value(presence[rid]):
            d = solver.Value(day[rid])
            s = solver.Value(start_in_day[rid])
            dur = max(1, round(r.predicted_duration_hours or 2))
            actual_start = WEEK_START + timedelta(days=d, hours=s)
            actual_end = actual_start + timedelta(hours=dur)
            scheduled.append((r, actual_start, actual_end))
            total_delay += (r.predicted_delay_minutes or 0)
            total_priority_addressed += (r.priority_score or 0)

    completion_rate = round(100 * len(scheduled) / len(requests), 1) if requests else 0
    max_capacity_hours = PLANNING_DAYS * MAINTENANCE_WINDOW_HOURS * max(len(sections), 1)
    used_hours = sum(max(1, round(r.predicted_duration_hours or 2)) for r, _, _ in scheduled)
    block_utilization = round(100 * used_hours / max_capacity_hours, 1) if max_capacity_hours else 0
    asset_availability = round(100 - (used_hours / max_capacity_hours * 100), 1) if max_capacity_hours else 100

    overall_score = round(
        0.4 * completion_rate + 0.3 * asset_availability + 0.3 * (100 - min(total_delay / 10, 100)), 1
    )

    plan = PlanCandidate(
        plan_label=plan_label,
        strategy=strategy,
        total_delay_minutes=round(total_delay, 1),
        completion_rate=completion_rate,
        asset_availability=asset_availability,
        block_utilization=block_utilization,
        overall_score=overall_score,
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)

    for r, actual_start, actual_end in scheduled:
        item = ScheduleItem(
            plan_id=plan.id,
            block_request_id=r.id,
            scheduled_start=actual_start,
            scheduled_end=actual_end,
        )
        session.add(item)
    session.commit()

    print(f"\n{plan_label} ({strategy}):")
    print(f"  Requests scheduled : {len(scheduled)} / {len(requests)}")
    print(f"  Completion rate    : {completion_rate}%")
    print(f"  Total delay        : {round(total_delay,1)} min")
    print(f"  Asset availability : {asset_availability}%")
    print(f"  Block utilization  : {block_utilization}%")
    print(f"  Overall score      : {overall_score}")

    return plan


def run_optimization():
    """Callable entry point (used by both the CLI script and the API
    endpoint) -- ensures requests exist, clears prior plans, and solves
    all three weighting profiles fresh. Returns the list of created
    PlanCandidate objects."""
    ensure_block_requests()

    requests = session.query(BlockRequest).filter(BlockRequest.status == "Pending").all()
    if not requests:
        return []

    # clear previous plans/schedule so re-running always reflects the
    # CURRENT set of pending requests (this is what makes it genuinely
    # dynamic when a new defect/request is added)
    session.query(ScheduleItem).delete()
    session.query(PlanCandidate).delete()
    session.commit()

    plans = []
    plans.append(solve_plan(requests, w_priority=1, w_delay=5, plan_label="Plan A", strategy="operations_first"))
    plans.append(solve_plan(requests, w_priority=5, w_delay=1, plan_label="Plan B", strategy="maintenance_first"))
    plans.append(solve_plan(requests, w_priority=3, w_delay=3, plan_label="Plan C", strategy="balanced"))
    return [p for p in plans if p]


def main():
    print("Step 1: ensuring block requests exist with ML predictions...")
    print("Step 2: solving three weighting profiles...")
    plans = run_optimization()
    if not plans:
        print("[warn] no pending requests found -- nothing to optimize.")
        return
    print("\nDone. All three plans saved to the database (plan_candidates + schedule_items).")


if __name__ == "__main__":
    main()