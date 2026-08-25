from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Boolean,
    ForeignKey, Text
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'blocksync.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base = declarative_base()


class Section(Base):
    __tablename__ = "sections"
    id = Column(Integer, primary_key=True)
    section_id = Column(String, unique=True, index=True)
    from_station = Column(String)
    to_station = Column(String)
    distance_km = Column(Float, nullable=True)
    traffic_density = Column(Float, default=1.0)

    defects = relationship("Defect", back_populates="section")
    block_requests = relationship("BlockRequest", back_populates="section")


class Defect(Base):
    __tablename__ = "defects"
    id = Column(Integer, primary_key=True)
    department = Column(String)
    section_id = Column(Integer, ForeignKey("sections.id"))
    defect_type = Column(String)
    severity = Column(Integer)
    reported_date = Column(DateTime, default=datetime.utcnow)
    overdue_days = Column(Integer, default=0)
    status = Column(String, default="Open")

    section = relationship("Section", back_populates="defects")


class BlockRequest(Base):
    __tablename__ = "block_requests"
    id = Column(Integer, primary_key=True)
    department = Column(String)
    section_id = Column(Integer, ForeignKey("sections.id"))
    defect_id = Column(Integer, ForeignKey("defects.id"), nullable=True)
    requested_start = Column(DateTime)
    requested_end = Column(DateTime)
    priority_score = Column(Float, nullable=True)
    predicted_duration_hours = Column(Float, nullable=True)
    predicted_delay_minutes = Column(Float, nullable=True)
    status = Column(String, default="Pending")

    section = relationship("Section", back_populates="block_requests")


class PlanCandidate(Base):
    __tablename__ = "plan_candidates"
    id = Column(Integer, primary_key=True)
    plan_label = Column(String)
    strategy = Column(String)
    total_delay_minutes = Column(Float)
    completion_rate = Column(Float)
    asset_availability = Column(Float)
    block_utilization = Column(Float)
    overall_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class ScheduleItem(Base):
    __tablename__ = "schedule_items"
    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("plan_candidates.id"))
    block_request_id = Column(Integer, ForeignKey("block_requests.id"))
    scheduled_start = Column(DateTime)
    scheduled_end = Column(DateTime)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    hashed_password = Column(String)
    role = Column(String)


class Approval(Base):
    __tablename__ = "approvals"
    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("plan_candidates.id"))
    approved_by = Column(Integer, ForeignKey("users.id"))
    decision = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String)
    target_table = Column(String)
    target_id = Column(Integer)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


class ExecutionRecord(Base):
    __tablename__ = "execution_records"
    id = Column(Integer, primary_key=True)
    block_request_id = Column(Integer, ForeignKey("block_requests.id"))
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    status = Column(String, default="Pending")