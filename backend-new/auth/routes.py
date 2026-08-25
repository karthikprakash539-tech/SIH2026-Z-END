"""
BlockSync Graph Routes.

Place at: backend/routes/graph_routes.py

Exposes the railway network graph built by graph/network_builder.py,
plus the animated train schedule built by graph/train_schedule.py.
Mounted into main.py via app.include_router(graph_router) -- see the
main.py wiring alongside this file. Nothing existing in main.py is
modified beyond that.
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "models"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "graph"))

from fastapi import APIRouter, Depends
from sqlalchemy.orm import sessionmaker, Session as DBSession
from models import engine, Section
from network_builder import build_network
from train_schedule import build_train_schedules

router = APIRouter(prefix="/graph", tags=["graph"])

SessionLocal = sessionmaker(bind=engine)

TIMETABLE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "train_timetable.csv")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/network")
def get_network(db: DBSession = Depends(get_db)):
    """Returns the full railway network as nodes (stations/junctions)
    and edges (sections), with live open-defect and pending-block-request
    counts attached per edge for coloring conflicts in the UI."""
    return build_network(db)


@router.get("/train-schedule")
def get_train_schedule(db: DBSession = Depends(get_db)):
    """Returns real per-train stop timing (arrival/departure seconds,
    midnight-rollover already resolved) with each hop mapped to the
    matching Section id, for the frontend to animate moving markers
    along the network graph."""
    sections = db.query(Section).all()
    section_lookup = {
        frozenset((s.from_station, s.to_station)): {"section_id": s.section_id, "db_id": s.id}
        for s in sections
    }
    return build_train_schedules(TIMETABLE_PATH, section_lookup)
