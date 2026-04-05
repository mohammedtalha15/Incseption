# Ayuq — Real-Time AI Hypoglycemia Prediction System

A production-grade full-stack healthcare AI system that predicts hypoglycemia risk in real-time using simulated patient data, with intelligent explanations powered by Claude.

> **Ayuq** detects dangerous glucose patterns *before* they become emergencies — giving patients and clinicians time to act.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React + Vite)         http://localhost:5173   │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐  │
│  │Dashboard │ │ Alerts   │ │ Profile │ │ Simulator  │  │
│  │ Chart    │ │ Panel    │ │ Form    │ │ Controls   │  │
│  └────┬─────┘ └────┬─────┘ └────┬────┘ └─────┬──────┘  │
│       │ WebSocket   │ REST       │ REST        │ REST   │
└───────┼─────────────┼────────────┼─────────────┼────────┘
        ▼             ▼            ▼             ▼
┌─────────────────────────────────────────────────────────┐
│  Backend (FastAPI)              http://localhost:8000    │
│  ┌───────────┐ ┌──────────┐ ┌─────────┐ ┌───────────┐  │
│  │POST       │ │GET       │ │GET      │ │POST       │  │
│  │/reading   │ │/readings │ │/alerts  │ │/profile   │  │
│  └─────┬─────┘ └──────────┘ └─────────┘ └───────────┘  │
│        ▼                                                │
│  ┌─────────────────────────────────────────────────┐    │
│  │  AI Pipeline                                     │    │
│  │  Feature Builder → Risk Engine → Explanation LLM │    │
│  └──────────────────────────┬──────────────────────┘    │
│                             ▼                           │
│  ┌──────────────────────────────────────────┐           │
│  │  SQLite (readings, alerts, profiles)      │           │
│  └──────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────┘
        ▲
        │ HTTP POST (every 3-5s)
┌───────┴─────────────────────────────────────────────────┐
│  Simulator (Python)                                      │
│  3 patients × 7 days × 5-min intervals = 6,048 readings │
└─────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Backend

```bash
cd backend
pip install -r requirements.txt

# Optional: Set Claude API key for AI explanations
# cp .env.example .env && edit .env

python -m uvicorn main:app --reload --port 8000
```

### 2. Generate Data

```bash
cd simulator
python generator.py
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Start Streaming

Either use the UI **Stream** button, or:
```bash
cd simulator
python streamer.py --speed 5 --interval 2
```

Open **http://localhost:5173** to see the dashboard.

---

## Features

### 🧠 AI Risk Engine

| Factor | Weight | What it measures |
|--------|--------|------------------|
| Glucose Trend | **35%** | Rate of change — the most critical predictor |
| Glucose Level | 25% | Absolute glucose value |
| Insulin Recency | 15% | Active insulin window (onset→peak→decline) |
| Meal Gap | 10% | Time since last carbohydrate intake |
| Time of Day | 10% | Nocturnal risk amplification |
| Activity Level | 5% | Exercise-induced glucose consumption |

### 🔔 Smart Alerts
- Triggered when risk exceeds 60/100
- AI-generated 2-sentence explanations (Claude or rule-based fallback)
- Predicted time to hypoglycemic event

### 📊 3 Hypo Scenarios
1. **Post-exercise crash** — Glucose 140→55 after vigorous activity
2. **Night-time insulin crash** — Glucose 120→50 during 2-4 AM
3. **Skipped meal slow drop** — Glucose 100→60 over 3 hours

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/reading` | Process new CGM reading through AI pipeline |
| `GET` | `/readings/{id}?hours=6` | Historical readings |
| `GET` | `/alerts/{id}?limit=50` | Alert history with explanations |
| `POST` | `/profile` | Create/update patient profile |
| `GET` | `/patients` | List all patients |
| `WS` | `/ws/{id}` | Real-time data stream |
| `POST` | `/simulator/start?speed=5` | Start simulator |
| `POST` | `/simulator/stop` | Stop simulator |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, Vite, Recharts, Lucide Icons |
| Backend | FastAPI, SQLAlchemy, Pydantic |
| AI | Rule-based scoring engine + Claude API |
| Database | SQLite |
| Design | Anthriq-aligned (Inter font, warm beige, orange accent) |

---

## Extensibility

- **ML Model**: Replace `RiskEngine.score()` with a trained model
- **Real CGM**: Swap simulator with Dexcom/Libre API integration
- **Database**: Change `DATABASE_URL` to PostgreSQL
- **LLM**: Swap Claude for any LLM provider
