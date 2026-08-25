"""
BlockSync Constraint Engine.

Place at: backend/constraints/constraint_engine.py

This module contains pure functions that check whether a proposed
BlockRequest conflicts with existing ones. No ML, no optimization --
just deterministic railway-safety rules, which is exactly right for
constraints that must be 100% explainable and enforceable.

Import and use it like:

    from constraint_engine import check_all_conflicts

    conflicts = check_all_conflicts(new_request, existing_requests)
    if conflicts:
        for c in conflicts:
            print(c["reason"])
"""

from datetime import datetime


def _overlaps(start_a, end_a, start_b, end_b):
    """True if [start_a, end_a) overlaps [start_b, end_b)."""
    return start_a < end_b and start_b < end_a


def check_track_conflict(new_req, existing_req):
    """Same section + overlapping time window = conflict.
    new_req / existing_req are dict-like objects with:
        section_id, requested_start, requested_end
    """
    if new_req["section_id"] != existing_req["section_id"]:
        return None
    if not _overlaps(
        new_req["requested_start"], new_req["requested_end"],
        existing_req["requested_start"], existing_req["requested_end"]
    ):
        return None
    return {
        "type": "track_conflict",
        "with_request_id": existing_req.get("id"),
        "reason": (
            f"Section {new_req['section_id']} already has a request "
            f"({existing_req.get('department')}) overlapping this time window."
        ),
    }


def check_train_conflict(new_req, train_movements):
    """A block overlapping a scheduled train movement on the same section
    is not allowed. train_movements is a list of dicts:
        {section_id, train_no, departure, arrival}
    """
    conflicts = []
    for tm in train_movements:
        if tm["section_id"] != new_req["section_id"]:
            continue
        if _overlaps(
            new_req["requested_start"], new_req["requested_end"],
            tm["departure"], tm["arrival"]
        ):
            conflicts.append({
                "type": "train_conflict",
                "train_no": tm["train_no"],
                "reason": (
                    f"Block overlaps scheduled train {tm['train_no']} "
                    f"on section {new_req['section_id']}."
                ),
            })
    return conflicts


def check_resource_conflict(new_req, existing_req, resource_key="department"):
    """Same crew/department + overlapping time on ANY section = conflict
    (a department's crew can't be in two places at once)."""
    if new_req[resource_key] != existing_req[resource_key]:
        return None
    if new_req["section_id"] == existing_req["section_id"]:
        return None  # already caught by track_conflict, avoid duplicate report
    if not _overlaps(
        new_req["requested_start"], new_req["requested_end"],
        existing_req["requested_start"], existing_req["requested_end"]
    ):
        return None
    return {
        "type": "resource_conflict",
        "with_request_id": existing_req.get("id"),
        "reason": (
            f"{new_req[resource_key]} crew is already assigned to another "
            f"block in this time window."
        ),
    }


def check_time_window(new_req, allowed_start_hour=0, allowed_end_hour=6):
    """Maintenance blocks should fall inside the allowed low-traffic
    window (default 00:00-06:00). Returns a violation dict or None."""
    start_hour = new_req["requested_start"].hour
    end_hour = new_req["requested_end"].hour
    if start_hour < allowed_start_hour or end_hour > allowed_end_hour:
        return {
            "type": "time_window_violation",
            "reason": (
                f"Requested window {new_req['requested_start'].strftime('%H:%M')}-"
                f"{new_req['requested_end'].strftime('%H:%M')} falls outside the "
                f"allowed maintenance window ({allowed_start_hour:02d}:00-{allowed_end_hour:02d}:00)."
            ),
        }
    return None


def check_safety_constraint(new_req):
    """Traction (TDMS) work requires isolation before start and
    re-energization clearance after end -- modeled here as a minimum
    duration requirement (traction work needs at least 1 hour to safely
    isolate + reenergize around the actual repair)."""
    if new_req.get("department") != "TDMS":
        return None
    duration_hours = (new_req["requested_end"] - new_req["requested_start"]).total_seconds() / 3600
    if duration_hours < 1.0:
        return {
            "type": "safety_constraint_violation",
            "reason": (
                "Traction (TDMS) blocks must be at least 1 hour to allow safe "
                "isolation and re-energization around the repair work."
            ),
        }
    return None


def check_department_dependency(new_req, existing_req):
    """If modeled: Signal (SMMS) maintenance on a section should not be
    scheduled before Track (TMS) maintenance on the SAME section has
    completed, when both are pending in the same period."""
    if new_req["section_id"] != existing_req["section_id"]:
        return None
    if new_req["department"] != "SMMS" or existing_req["department"] != "TMS":
        return None
    if existing_req.get("status") == "Resolved":
        return None
    if new_req["requested_start"] < existing_req["requested_end"]:
        return {
            "type": "dependency_violation",
            "with_request_id": existing_req.get("id"),
            "reason": (
                "Signal maintenance on this section is scheduled before "
                "pending track maintenance completes."
            ),
        }
    return None


def check_all_conflicts(new_req, existing_requests, train_movements=None):
    """Runs every applicable check against a new request and returns a
    flat list of all conflicts found (empty list = fully valid, schedulable
    request)."""
    conflicts = []

    for existing in existing_requests:
        if existing.get("id") == new_req.get("id"):
            continue  # don't compare a request against itself

        track = check_track_conflict(new_req, existing)
        if track:
            conflicts.append(track)

        resource = check_resource_conflict(new_req, existing)
        if resource:
            conflicts.append(resource)

        dependency = check_department_dependency(new_req, existing)
        if dependency:
            conflicts.append(dependency)

    if train_movements:
        conflicts.extend(check_train_conflict(new_req, train_movements))

    time_violation = check_time_window(new_req)
    if time_violation:
        conflicts.append(time_violation)

    safety_violation = check_safety_constraint(new_req)
    if safety_violation:
        conflicts.append(safety_violation)

    return conflicts


if __name__ == "__main__":
    # quick self-test with sample data
    from datetime import datetime

    req_a = {
        "id": 1, "department": "TMS", "section_id": 3,
        "requested_start": datetime(2026, 8, 25, 1, 0),
        "requested_end": datetime(2026, 8, 25, 3, 0),
        "status": "Pending",
    }
    req_b = {
        "id": 2, "department": "SMMS", "section_id": 3,
        "requested_start": datetime(2026, 8, 25, 2, 0),
        "requested_end": datetime(2026, 8, 25, 4, 0),
        "status": "Pending",
    }

    print("Testing overlapping same-section requests (should show conflicts):")
    result = check_all_conflicts(req_b, [req_a])
    for c in result:
        print(" -", c["reason"])
    if not result:
        print(" - no conflicts found (unexpected for this test case)")