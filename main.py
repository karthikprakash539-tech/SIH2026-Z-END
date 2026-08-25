"""
BlockSync FastAPI backend -- FULL version including Governance Layer
+ Railway Network Graph.

Place at: backend/main.py (replaces the earlier version entirely)

Run from inside backend/ folder:
    uvicorn main:app --reload

Then open:
    http://127.0.0.1:8000/docs
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "models"))
sys.path.append(os.path.join(os.path.dirname(__file__), "auth"))
sys.path.append(os.path.join(os.path.dirname(__file__), "routes"))
from graph_routes import router as graph_router

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker, Session as DBSession
from datetime import datetime
from typing import Optional
import json

from models import (
    engine, Section, Defect, BlockRequest, PlanCandidate,
    ScheduleItem, User, Approval, AuditLog
)
from security import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_role,
)

app = FastAPI(title="BlockSync API", version="0.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph_router)

SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def write_audit_log(db, actor_id, action, target_table, target_id, old_value=None, new_value=None):
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_table=target_table,
        target_id=target_id,
        old_value=json.dumps(old_value) if old_value is not None else None,
        new_value=json.dumps(new_value) if new_value is not None else None,
    )
    db.add(entry)
    db.commit()


# ---------------------------------------------------------------------------
# Response / request shapes
# ---------------------------------------------------------------------------

class SectionOut(BaseModel):
    id: int
    section_id: str
    from_station: str
    to_station: str
    distance_km: float
    traffic_density: float

    class Config:
        from_attributes = True


class DefectOut(BaseModel):
    id: int
    department: str
    section_id: int
    defect_type: str
    severity: int
    overdue_days: int
    status: str

    class Config:
        from_attributes = True


class BlockRequestIn(BaseModel):
    department: str
    section_id: int
    defect_id: Optional[int] = None
    requested_start: datetime
    requested_end: datetime


class BlockRequestOut(BaseModel):
    id: int
    department: str
    section_id: int
    defect_id: Optional[int]
    requested_start: datetime
    requested_end: datetime
    priority_score: Optional[float]
    predicted_duration_hours: Optional[float]
    predicted_delay_minutes: Optional[float]
    status: str

    class Config:
        from_attributes = True


class PlanOut(BaseModel):
    id: int
    plan_label: str
    strategy: str
    total_delay_minutes: float
    completion_rate: float
    asset_availability: float
    block_utilization: float
    overall_score: float

    class Config:
        from_attributes = True


class ScheduleItemOut(BaseModel):
    id: int
    plan_id: int
    block_request_id: int
    scheduled_start: datetime
    scheduled_end: datetime

    class Config:
        from_attributes = True


class ApprovalDecisionOut(BaseModel):
    id: int
    plan_id: int
    approved_by: int
    decision: str
    timestamp: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.post("/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role}


@app.get("/auth/me")
def read_current_user(current_user=Depends(get_current_user)):
    return {"username": current_user.username, "role": current_user.role}


# ---------------------------------------------------------------------------
# Public data routes (read-only, no login required for a hackathon demo)
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"message": "BlockSync API is running"}


@app.get("/sections", response_model=list[SectionOut])
def list_sections(db: DBSession = Depends(get_db)):
    return db.query(Section).all()


@app.get("/defects", response_model=list[DefectOut])
def list_defects(department: Optional[str] = None, db: DBSession = Depends(get_db)):
    query = db.query(Defect)
    if department:
        query = query.filter(Defect.department == department.upper())
    return query.all()


@app.post("/requests", response_model=BlockRequestOut)
def create_request(req: BlockRequestIn, db: DBSession = Depends(get_db)):
    section = db.query(Section).filter(Section.id == req.section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    new_request = BlockRequest(
        department=req.department,
        section_id=req.section_id,
        defect_id=req.defect_id,
        requested_start=req.requested_start,
        requested_end=req.requested_end,
        status="Pending",
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request


@app.get("/requests", response_model=list[BlockRequestOut])
def list_requests(db: DBSession = Depends(get_db)):
    return db.query(BlockRequest).all()


# ---------------------------------------------------------------------------
# Plan / Decision Support routes
# ---------------------------------------------------------------------------

@app.get("/plans", response_model=list[PlanOut])
def list_plans(db: DBSession = Depends(get_db)):
    """Returns every generated plan (Plan A/B/C from the optimizer),
    ranked by overall_score descending -- this is your Decision Support
    comparison view."""
    return db.query(PlanCandidate).order_by(PlanCandidate.overall_score.desc()).all()


@app.get("/plans/{plan_id}/schedule", response_model=list[ScheduleItemOut])
def get_plan_schedule(plan_id: int, db: DBSession = Depends(get_db)):
    items = db.query(ScheduleItem).filter(ScheduleItem.plan_id == plan_id).all()
    if not items:
        raise HTTPException(status_code=404, detail="No schedule items found for this plan")
    return items


@app.post("/plans/{plan_id}/approve", response_model=ApprovalDecisionOut)
def approve_plan(
    plan_id: int,
    db: DBSession = Depends(get_db),
    current_user=Depends(require_role("engineering_officer", "signal_officer", "traction_officer", "admin")),
):
    plan = db.query(PlanCandidate).filter(PlanCandidate.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    approval = Approval(plan_id=plan_id, approved_by=current_user.id, decision="Approved")
    db.add(approval)
    db.commit()
    db.refresh(approval)

    write_audit_log(
        db, actor_id=current_user.id, action="APPROVE_PLAN",
        target_table="plan_candidates", target_id=plan_id,
        old_value={"status": "Pending"}, new_value={"status": "Approved"},
    )
    return approval


@app.post("/plans/{plan_id}/reject", response_model=ApprovalDecisionOut)
def reject_plan(
    plan_id: int,
    db: DBSession = Depends(get_db),
    current_user=Depends(require_role("engineering_officer", "signal_officer", "traction_officer", "admin")),
):
    plan = db.query(PlanCandidate).filter(PlanCandidate.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    approval = Approval(plan_id=plan_id, approved_by=current_user.id, decision="Rejected")
    db.add(approval)
    db.commit()
    db.refresh(approval)

    write_audit_log(
        db, actor_id=current_user.id, action="REJECT_PLAN",
        target_table="plan_candidates", target_id=plan_id,
        old_value={"status": "Pending"}, new_value={"status": "Rejected"},
    )
    return approval


# ---------------------------------------------------------------------------
# Audit log route (admin-only -- shows the governance layer is real)
# ---------------------------------------------------------------------------

@app.get("/audit-log")
def get_audit_log(db: DBSession = Depends(get_db), current_user=Depends(require_role("admin"))):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
    return [
        {
            "id": log.id,
            "actor_id": log.actor_id,
            "action": log.action,
            "target_table": log.target_table,
            "target_id": log.target_id,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "timestamp": log.timestamp,
        }
        for log in logs
    ]


# ---------------------------------------------------------------------------
# Dashboard metrics
# ---------------------------------------------------------------------------

@app.get("/dashboard/metrics")
def dashboard_metrics(db: DBSession = Depends(get_db)):
    total_defects = db.query(Defect).count()
    open_defects = db.query(Defect).filter(Defect.status == "Open").count()
    total_requests = db.query(BlockRequest).count()
    plans = db.query(PlanCandidate).all()
    best_plan = max(plans, key=lambda p: p.overall_score) if plans else None

    return {
        "total_defects": total_defects,
        "open_defects": open_defects,
        "total_requests": total_requests,
        "plans_generated": len(plans),
        "best_plan": best_plan.plan_label if best_plan else None,
        "best_plan_score": best_plan.overall_score if best_plan else None,
    }


# ---------------------------------------------------------------------------
# Dynamic re-optimization (What-If Engine)
# ---------------------------------------------------------------------------

class EmergencyDefectIn(BaseModel):
    department: str
    section_id: int
    defect_type: str
    severity: int = 5  # emergency defects default to critical


@app.post("/schedule/generate")
def regenerate_schedule():
    """Re-runs the full optimizer against whatever requests currently
    exist -- this is what makes the system genuinely dynamic. Call this
    after adding a new defect/emergency to see the plans update live."""
    sys.path.append(os.path.join(os.path.dirname(__file__), "optimizer"))
    import optimize
    plans = optimize.run_optimization()
    return {
        "message": f"Re-optimized: {len(plans)} plans generated",
        "plans": [p.plan_label for p in plans],
    }


@app.post("/defects/emergency")
def add_emergency_defect(defect: EmergencyDefectIn, db: DBSession = Depends(get_db)):
    """Simulates a newly-discovered critical defect (Phase 19's 'Event 2'
    scenario) -- creates the defect, then immediately triggers
    re-optimization so the plans reflect it live."""
    section = db.query(Section).filter(Section.id == defect.section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    new_defect = Defect(
        department=defect.department,
        section_id=defect.section_id,
        defect_type=defect.defect_type,
        severity=defect.severity,
        overdue_days=0,
        status="Open",
    )
    db.add(new_defect)
    db.commit()
    db.refresh(new_defect)

    sys.path.append(os.path.join(os.path.dirname(__file__), "optimizer"))
    import optimize
    plans = optimize.run_optimization()

    return {
        "message": f"Emergency defect #{new_defect.id} added and schedule re-optimized",
        "defect_id": new_defect.id,
        "plans_regenerated": [p.plan_label for p in plans],
    }
