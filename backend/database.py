"""
Ayuq — Database Layer

SQLite database with SQLAlchemy async for readings, alerts, and profiles.
"""

import os
from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Float, Integer, String, Text, Boolean,
    create_engine, event,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ayuq.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─── ORM Models ──────────────────────────────────────────

class ReadingRecord(Base):
    __tablename__ = "readings"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(String(10), index=True, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    glucose_mgdl = Column(Float, nullable=False)
    glucose_trend = Column(Float, default=0.0)
    last_meal_mins_ago = Column(Integer, default=0)
    meal_carbs_g = Column(Float, default=0.0)
    last_insulin_units = Column(Float, default=0.0)
    insulin_mins_ago = Column(Integer, default=0)
    activity_level = Column(String(20), default="rest")
    time_of_day = Column(String(20), default="morning")
    
    # Computed risk fields
    risk_score = Column(Float, default=0.0)
    risk_level = Column(String(10), default="LOW")
    predicted_time_to_event = Column(Float, nullable=True)
    contributing_factors = Column(Text, nullable=True)  # JSON string
    
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertRecord(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(String(10), index=True, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(10), nullable=False)
    glucose_mgdl = Column(Float, nullable=False)
    glucose_trend = Column(Float, default=0.0)
    predicted_time_to_event = Column(Float, nullable=True)
    contributing_factors = Column(Text, nullable=True)  # JSON string
    explanation = Column(Text, nullable=True)
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProfileRecord(Base):
    __tablename__ = "profiles"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=True)
    diabetes_type = Column(String(20), nullable=True)
    lifestyle = Column(String(200), nullable=True)
    medications = Column(Text, nullable=True)
    baseline_glucose = Column(Float, default=100.0)
    typical_meals = Column(Text, nullable=True)  # JSON string
    insulin_regimen = Column(String(200), nullable=True)
    basal_insulin = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── Database Initialization ────────────────────────────

def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
    print("✓ Database initialized")


def get_db():
    """Dependency for FastAPI — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("Database tables created successfully.")
