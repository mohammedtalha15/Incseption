"""
Ayuq — Pydantic Models

Request/response schemas for the API layer.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ActivityLevel(str, Enum):
    REST = "rest"
    LIGHT = "light"
    MODERATE = "moderate"
    HIGH = "high"


class TimeOfDay(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"


# ─── Request Schemas ─────────────────────────────────────

class ReadingInput(BaseModel):
    """Schema for incoming CGM readings from the simulator."""
    timestamp: str
    glucose_mgdl: float = Field(..., ge=20, le=500)
    glucose_trend: float = 0.0
    last_meal_mins_ago: int = Field(0, ge=0)
    meal_carbs_g: float = Field(0, ge=0)
    last_insulin_units: float = Field(0, ge=0)
    insulin_mins_ago: int = Field(0, ge=0)
    activity_level: str = "rest"
    time_of_day: str = "morning"
    patient_id: str


class ProfileInput(BaseModel):
    """Schema for creating/updating patient profiles."""
    patient_id: str
    name: str
    age: Optional[int] = None
    diabetes_type: Optional[str] = None
    lifestyle: Optional[str] = None
    medications: Optional[str] = None
    baseline_glucose: float = 100.0
    typical_meals: Optional[List[str]] = None
    insulin_regimen: Optional[str] = None
    basal_insulin: Optional[float] = None


# ─── Response Schemas ────────────────────────────────────

class RiskAssessment(BaseModel):
    """Risk engine output."""
    risk_score: float = Field(..., ge=0, le=100)
    risk_level: RiskLevel
    predicted_time_to_event: Optional[float] = None
    contributing_factors: List[str] = []
    alert_generated: bool = False
    explanation: Optional[str] = None


class ReadingResponse(BaseModel):
    """Response when a reading is processed."""
    reading: ReadingInput
    risk_assessment: RiskAssessment
    features: dict = {}


class ReadingHistoryItem(BaseModel):
    """A single reading in history response."""
    id: int
    timestamp: str
    glucose_mgdl: float
    glucose_trend: float
    risk_score: float
    risk_level: str
    last_meal_mins_ago: int
    insulin_mins_ago: int
    activity_level: str
    predicted_time_to_event: Optional[float] = None


class AlertResponse(BaseModel):
    """A single alert in alerts response."""
    id: int
    patient_id: str
    timestamp: str
    risk_score: float
    risk_level: str
    glucose_mgdl: float
    glucose_trend: float
    predicted_time_to_event: Optional[float] = None
    contributing_factors: List[str] = []
    explanation: Optional[str] = None
    acknowledged: bool = False
    created_at: str


class PatientSummary(BaseModel):
    """Summary info about a patient."""
    patient_id: str
    name: str
    diabetes_type: Optional[str] = None
    latest_glucose: Optional[float] = None
    latest_risk_score: Optional[float] = None
    latest_risk_level: Optional[str] = None
    total_alerts: int = 0


class ProfileResponse(BaseModel):
    """Response for patient profile."""
    patient_id: str
    name: str
    age: Optional[int] = None
    diabetes_type: Optional[str] = None
    lifestyle: Optional[str] = None
    medications: Optional[str] = None
    baseline_glucose: float = 100.0
    typical_meals: Optional[List[str]] = None
    insulin_regimen: Optional[str] = None
    basal_insulin: Optional[float] = None
