"""
Ayuq — FastAPI Backend

Real-time hypoglycemia risk prediction API.
Processes CGM readings, computes risk scores, generates alerts with
AI-powered explanations, and streams updates via WebSocket.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db, init_db, ReadingRecord, AlertRecord, ProfileRecord
from models import (
    ReadingInput, ReadingResponse, RiskAssessment,
    ProfileInput, ProfileResponse, PatientSummary,
    ReadingHistoryItem, AlertResponse,
)
from ai.feature_builder import FeatureBuilder
from ai.risk_engine import RiskEngine
from ai.explanation_engine import ExplanationEngine

# ─── Logging ──────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("ayuq")

# ─── AI Pipeline Singletons ──────────────────────────────
feature_builder = FeatureBuilder(window_size=12)
risk_engine = RiskEngine()
explanation_engine = ExplanationEngine()

# ─── WebSocket Connection Manager ─────────────────────────
class ConnectionManager:
    """Manage WebSocket connections per patient."""
    
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, patient_id: str, ws: WebSocket):
        await ws.accept()
        if patient_id not in self.connections:
            self.connections[patient_id] = []
        self.connections[patient_id].append(ws)
        logger.info(f"WebSocket connected for {patient_id} (total: {len(self.connections[patient_id])})")
    
    def disconnect(self, patient_id: str, ws: WebSocket):
        if patient_id in self.connections:
            self.connections[patient_id] = [c for c in self.connections[patient_id] if c != ws]
            logger.info(f"WebSocket disconnected for {patient_id}")
    
    async def broadcast(self, patient_id: str, data: dict):
        """Broadcast data to all connections for a patient."""
        if patient_id not in self.connections:
            return
        dead = []
        for ws in self.connections[patient_id]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.connections[patient_id].remove(ws)

manager = ConnectionManager()

# ─── Simulator Process ────────────────────────────────────
simulator_process: Optional[subprocess.Popen] = None

# ─── App Lifecycle ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB on startup."""
    init_db()
    logger.info("Ayuq backend started ✓")
    yield
    logger.info("Ayuq backend shutting down")

# ─── FastAPI App ──────────────────────────────────────────
app = FastAPI(
    title="Ayuq — AI Hypoglycemia Prediction",
    description="Real-time risk scoring and alert system for hypoglycemia prevention",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── ENDPOINTS ────────────────────────────────────────────

@app.post("/reading", response_model=ReadingResponse)
async def process_reading(reading: ReadingInput, db: Session = Depends(get_db)):
    """
    Core pipeline: Accept reading → build features → score risk → 
    generate explanation if needed → store → broadcast.
    """
    reading_dict = reading.model_dump()
    
    # Step 1: Feature Engineering
    features = feature_builder.build_features(reading_dict)
    
    # Step 2: Risk Scoring
    risk_result = risk_engine.score(reading_dict, features)
    
    # Step 3: Explanation (if high risk)
    explanation = None
    alert_generated = False
    
    if risk_result["risk_score"] >= 60:
        explanation = await explanation_engine.generate_explanation(
            reading_dict, features, risk_result
        )
        alert_generated = True
        
        # Store alert
        alert = AlertRecord(
            patient_id=reading.patient_id,
            timestamp=datetime.fromisoformat(reading.timestamp),
            risk_score=risk_result["risk_score"],
            risk_level=risk_result["risk_level"],
            glucose_mgdl=reading.glucose_mgdl,
            glucose_trend=features.get("glucose_trend_computed", 0),
            predicted_time_to_event=risk_result.get("predicted_time_to_event"),
            contributing_factors=json.dumps(risk_result.get("contributing_factors", [])),
            explanation=explanation,
        )
        db.add(alert)
    
    # Step 4: Store reading
    record = ReadingRecord(
        patient_id=reading.patient_id,
        timestamp=datetime.fromisoformat(reading.timestamp),
        glucose_mgdl=reading.glucose_mgdl,
        glucose_trend=features.get("glucose_trend_computed", reading.glucose_trend),
        last_meal_mins_ago=reading.last_meal_mins_ago,
        meal_carbs_g=reading.meal_carbs_g,
        last_insulin_units=reading.last_insulin_units,
        insulin_mins_ago=reading.insulin_mins_ago,
        activity_level=reading.activity_level,
        time_of_day=reading.time_of_day,
        risk_score=risk_result["risk_score"],
        risk_level=risk_result["risk_level"],
        predicted_time_to_event=risk_result.get("predicted_time_to_event"),
        contributing_factors=json.dumps(risk_result.get("contributing_factors", [])),
    )
    db.add(record)
    db.commit()
    
    # Step 5: Build response
    risk_assessment = RiskAssessment(
        risk_score=risk_result["risk_score"],
        risk_level=risk_result["risk_level"],
        predicted_time_to_event=risk_result.get("predicted_time_to_event"),
        contributing_factors=risk_result.get("contributing_factors", []),
        alert_generated=alert_generated,
        explanation=explanation,
    )
    
    response = ReadingResponse(
        reading=reading,
        risk_assessment=risk_assessment,
        features=features,
    )
    
    # Step 6: Broadcast via WebSocket
    await manager.broadcast(reading.patient_id, {
        "type": "reading",
        "data": {
            "timestamp": reading.timestamp,
            "glucose_mgdl": reading.glucose_mgdl,
            "glucose_trend": features.get("glucose_trend_computed", 0),
            "risk_score": risk_result["risk_score"],
            "risk_level": risk_result["risk_level"],
            "predicted_time_to_event": risk_result.get("predicted_time_to_event"),
            "contributing_factors": risk_result.get("contributing_factors", []),
            "last_meal_mins_ago": reading.last_meal_mins_ago,
            "insulin_mins_ago": reading.insulin_mins_ago,
            "activity_level": reading.activity_level,
            "alert_generated": alert_generated,
            "explanation": explanation,
        }
    })
    
    return response


@app.get("/readings/{patient_id}")
async def get_readings(
    patient_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """Get readings for a patient over the last N hours."""
    records = (
        db.query(ReadingRecord)
        .filter(ReadingRecord.patient_id == patient_id)
        .order_by(desc(ReadingRecord.id))
        .limit(hours * 12)  # 12 readings per hour (every 5 min)
        .all()
    )
    
    records.reverse()  # Oldest first
    
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat() if r.timestamp else "",
            "glucose_mgdl": r.glucose_mgdl,
            "glucose_trend": r.glucose_trend,
            "risk_score": r.risk_score,
            "risk_level": r.risk_level,
            "last_meal_mins_ago": r.last_meal_mins_ago,
            "insulin_mins_ago": r.insulin_mins_ago,
            "activity_level": r.activity_level,
            "predicted_time_to_event": r.predicted_time_to_event,
        }
        for r in records
    ]


@app.get("/alerts/{patient_id}")
async def get_alerts(
    patient_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get all high-risk alerts for a patient with explanations."""
    alerts = (
        db.query(AlertRecord)
        .filter(AlertRecord.patient_id == patient_id)
        .order_by(desc(AlertRecord.created_at))
        .limit(limit)
        .all()
    )
    
    return [
        {
            "id": a.id,
            "patient_id": a.patient_id,
            "timestamp": a.timestamp.isoformat() if a.timestamp else "",
            "risk_score": a.risk_score,
            "risk_level": a.risk_level,
            "glucose_mgdl": a.glucose_mgdl,
            "glucose_trend": a.glucose_trend,
            "predicted_time_to_event": a.predicted_time_to_event,
            "contributing_factors": json.loads(a.contributing_factors) if a.contributing_factors else [],
            "explanation": a.explanation,
            "acknowledged": a.acknowledged,
            "created_at": a.created_at.isoformat() if a.created_at else "",
        }
        for a in alerts
    ]


@app.post("/profile")
async def upsert_profile(profile: ProfileInput, db: Session = Depends(get_db)):
    """Create or update a patient profile."""
    existing = (
        db.query(ProfileRecord)
        .filter(ProfileRecord.patient_id == profile.patient_id)
        .first()
    )
    
    if existing:
        for key, value in profile.model_dump(exclude_unset=True).items():
            if key == "typical_meals" and value is not None:
                setattr(existing, key, json.dumps(value))
            else:
                setattr(existing, key, value)
        db.commit()
        return {"status": "updated", "patient_id": profile.patient_id}
    else:
        record = ProfileRecord(
            patient_id=profile.patient_id,
            name=profile.name,
            age=profile.age,
            diabetes_type=profile.diabetes_type,
            lifestyle=profile.lifestyle,
            medications=profile.medications,
            baseline_glucose=profile.baseline_glucose,
            typical_meals=json.dumps(profile.typical_meals) if profile.typical_meals else None,
            insulin_regimen=profile.insulin_regimen,
            basal_insulin=profile.basal_insulin,
        )
        db.add(record)
        db.commit()
        return {"status": "created", "patient_id": profile.patient_id}


@app.get("/profile/{patient_id}")
async def get_profile(patient_id: str, db: Session = Depends(get_db)):
    """Get a patient's profile."""
    record = (
        db.query(ProfileRecord)
        .filter(ProfileRecord.patient_id == patient_id)
        .first()
    )
    
    if not record:
        raise HTTPException(status_code=404, detail=f"Profile not found for {patient_id}")
    
    return {
        "patient_id": record.patient_id,
        "name": record.name,
        "age": record.age,
        "diabetes_type": record.diabetes_type,
        "lifestyle": record.lifestyle,
        "medications": record.medications,
        "baseline_glucose": record.baseline_glucose,
        "typical_meals": json.loads(record.typical_meals) if record.typical_meals else [],
        "insulin_regimen": record.insulin_regimen,
        "basal_insulin": record.basal_insulin,
    }


@app.get("/patients")
async def get_patients(db: Session = Depends(get_db)):
    """List all patients with summary data."""
    # Get unique patient IDs from readings
    from sqlalchemy import func, distinct
    
    patient_ids = [
        r[0] for r in 
        db.query(distinct(ReadingRecord.patient_id)).all()
    ]
    
    # Also check profiles
    profile_ids = [
        r[0] for r in 
        db.query(distinct(ProfileRecord.patient_id)).all()
    ]
    
    all_ids = list(set(patient_ids + profile_ids))
    
    if not all_ids:
        # Return default patients
        all_ids = ["P001", "P002", "P003"]
    
    patients = []
    for pid in sorted(all_ids):
        profile = db.query(ProfileRecord).filter(ProfileRecord.patient_id == pid).first()
        latest = (
            db.query(ReadingRecord)
            .filter(ReadingRecord.patient_id == pid)
            .order_by(desc(ReadingRecord.id))
            .first()
        )
        alert_count = (
            db.query(func.count(AlertRecord.id))
            .filter(AlertRecord.patient_id == pid)
            .scalar()
        )
        
        patients.append({
            "patient_id": pid,
            "name": profile.name if profile else f"Patient {pid}",
            "diabetes_type": profile.diabetes_type if profile else None,
            "latest_glucose": latest.glucose_mgdl if latest else None,
            "latest_risk_score": latest.risk_score if latest else None,
            "latest_risk_level": latest.risk_level if latest else None,
            "total_alerts": alert_count or 0,
        })
    
    return patients


# ─── WebSocket ────────────────────────────────────────────

@app.websocket("/ws/{patient_id}")
async def websocket_endpoint(websocket: WebSocket, patient_id: str):
    """Real-time data stream for a patient."""
    await manager.connect(patient_id, websocket)
    try:
        while True:
            # Keep connection alive, listen for client messages
            data = await websocket.receive_text()
            # Client can send ping or other commands
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(patient_id, websocket)


# ─── Simulator Control ───────────────────────────────────

@app.post("/simulator/start")
async def start_simulator(
    speed: float = Query(default=1.0, ge=0.5, le=20.0),
    interval: float = Query(default=4.0, ge=0.5, le=10.0),
):
    """Start the data simulator as a background process."""
    global simulator_process
    
    if simulator_process and simulator_process.poll() is None:
        return {"status": "already_running", "pid": simulator_process.pid}
    
    simulator_path = os.path.join(os.path.dirname(__file__), "..", "simulator", "streamer.py")
    simulator_path = os.path.abspath(simulator_path)
    
    if not os.path.exists(simulator_path):
        raise HTTPException(status_code=404, detail="Simulator not found")
    
    # Check if data file exists, generate if not
    data_path = os.path.join(os.path.dirname(simulator_path), "simulated_data.json")
    if not os.path.exists(data_path):
        gen_path = os.path.join(os.path.dirname(simulator_path), "generator.py")
        logger.info("Generating simulated data...")
        subprocess.run([sys.executable, gen_path], cwd=os.path.dirname(gen_path))
    
    simulator_process = subprocess.Popen(
        [sys.executable, simulator_path, "--speed", str(speed), "--interval", str(interval)],
        cwd=os.path.dirname(simulator_path),
    )
    
    logger.info(f"Simulator started (PID: {simulator_process.pid}, speed: {speed}x)")
    return {"status": "started", "pid": simulator_process.pid, "speed": speed}


@app.post("/simulator/stop")
async def stop_simulator():
    """Stop the data simulator."""
    global simulator_process
    
    if simulator_process and simulator_process.poll() is None:
        simulator_process.terminate()
        simulator_process.wait(timeout=5)
        pid = simulator_process.pid
        simulator_process = None
        return {"status": "stopped", "pid": pid}
    
    return {"status": "not_running"}


@app.get("/simulator/status")
async def simulator_status():
    """Check simulator status."""
    global simulator_process
    
    if simulator_process and simulator_process.poll() is None:
        return {"status": "running", "pid": simulator_process.pid}
    return {"status": "stopped"}


# ─── Health Check ─────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ayuq",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }
