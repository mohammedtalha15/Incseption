"""
Ayuq — Patient Data Generator

Generates 7 days of simulated CGM data for 3 fictional patients.
Each patient has distinct profiles and experiences different hypo scenarios.
Interval: every 5 minutes (~2016 readings per patient, ~6048 total).
"""

import json
import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from scenarios import SCENARIOS, ScenarioReading


# Patient profiles
PATIENTS = {
    "P001": {
        "name": "Arjun Mehta",
        "age": 28,
        "diabetes_type": "Type 1",
        "lifestyle": "Active — runs and cycles regularly",
        "primary_scenario": "post_exercise_crash",
        "baseline_glucose": 110,
        "typical_meals": ["7:30 AM", "12:30 PM", "7:00 PM"],
        "insulin_regimen": "Bolus before meals + correction",
        "basal_insulin": 22,
    },
    "P002": {
        "name": "Fatima Rahman",
        "age": 45,
        "diabetes_type": "Type 2",
        "lifestyle": "Sedentary — office work",
        "primary_scenario": "nighttime_insulin_crash",
        "baseline_glucose": 130,
        "typical_meals": ["8:00 AM", "1:00 PM", "8:00 PM"],
        "insulin_regimen": "Long-acting evening insulin",
        "basal_insulin": 30,
    },
    "P003": {
        "name": "Carlos Vega",
        "age": 34,
        "diabetes_type": "Type 1",
        "lifestyle": "Irregular schedule — shift worker",
        "primary_scenario": "skipped_meal_drop",
        "baseline_glucose": 100,
        "typical_meals": ["9:00 AM", "2:00 PM", "9:00 PM"],
        "insulin_regimen": "Pump + bolus",
        "basal_insulin": 18,
    },
}


def _time_of_day(hour: int) -> str:
    """Categorize hour into time-of-day bucket."""
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"


def _normal_glucose(hour: int, baseline: float) -> float:
    """Generate a normal glucose value following natural circadian patterns."""
    # Dawn phenomenon: slight rise 4-8 AM
    # Post-meal rises around typical meal times
    # Lower overnight
    circadian = 10 * math.sin(math.pi * (hour - 6) / 12)
    noise = random.gauss(0, 5)
    return max(70, baseline + circadian + noise)


def _is_near_meal(current_time: datetime, meal_times: List[str]) -> tuple:
    """Check if current time is near a meal, return (is_meal, carbs, mins_since)."""
    for meal_str in meal_times:
        meal_hour, meal_min = map(int, meal_str.replace(" AM", "").replace(" PM", "").split(":"))
        if "PM" in meal_str and meal_hour != 12:
            meal_hour += 12
        elif "AM" in meal_str and meal_hour == 12:
            meal_hour = 0
        
        meal_dt = current_time.replace(hour=meal_hour, minute=meal_min, second=0)
        diff_mins = (current_time - meal_dt).total_seconds() / 60
        
        # Within 5 minutes of meal time = eating now
        if 0 <= diff_mins <= 5:
            carbs = random.choice([30, 45, 50, 60, 70])
            return True, carbs, 0
        # 5 min to 4 hours after meal
        elif 5 < diff_mins <= 240:
            return False, 0, int(diff_mins)
    
    return False, 0, 999  # No recent meal


def _compute_glucose_trend(readings: List[Dict], current_idx: int) -> float:
    """Compute glucose trend from recent readings (mg/dL per 5 min)."""
    if current_idx < 2:
        return 0.0
    
    recent = readings[max(0, current_idx - 3):current_idx]
    if len(recent) < 2:
        return 0.0
    
    # Simple linear regression over last few points
    deltas = []
    for i in range(1, len(recent)):
        deltas.append(recent[i]["glucose_mgdl"] - recent[i-1]["glucose_mgdl"])
    
    return round(sum(deltas) / len(deltas), 2) if deltas else 0.0


def generate_patient_data(
    patient_id: str,
    days: int = 7,
    interval_minutes: int = 5,
    start_date: Optional[datetime] = None,
) -> List[Dict]:
    """
    Generate complete simulated data for a patient.
    
    Returns a list of reading dicts matching the exact required schema.
    """
    patient = PATIENTS[patient_id]
    if start_date is None:
        start_date = datetime(2026, 3, 29, 0, 0, 0)
    
    readings = []
    total_minutes = days * 24 * 60
    steps = total_minutes // interval_minutes
    
    # Determine when scenarios happen
    scenario_fn = SCENARIOS[patient["primary_scenario"]]
    
    # Schedule 2-3 scenario events per week, spread across different days
    scenario_events = []
    for day in range(days):
        if random.random() < 0.4 or day in [1, 3, 5]:  # ~3 events per week
            if patient["primary_scenario"] == "post_exercise_crash":
                # Exercise crashes happen in afternoon/evening
                start_hour = random.choice([14, 15, 16, 17, 18])
            elif patient["primary_scenario"] == "nighttime_insulin_crash":
                # Night crashes happen after 10 PM
                start_hour = random.choice([22, 23])
            else:
                # Skipped meal drops happen mid-day
                start_hour = random.choice([11, 12, 13, 14])
            
            scenario_start = start_date + timedelta(days=day, hours=start_hour)
            scenario_readings = scenario_fn()
            scenario_events.append((scenario_start, scenario_readings))
    
    # Track last meal and insulin for context
    last_meal_time = start_date - timedelta(hours=2)
    last_meal_carbs = 45.0
    last_insulin_time = start_date - timedelta(hours=3)
    last_insulin_units = patient["basal_insulin"] / 3.0
    
    for step in range(steps):
        current_time = start_date + timedelta(minutes=step * interval_minutes)
        hour = current_time.hour
        
        # Check if we're inside a scenario
        in_scenario = False
        for sc_start, sc_readings in scenario_events:
            sc_idx = int((current_time - sc_start).total_seconds() / (interval_minutes * 60))
            if 0 <= sc_idx < len(sc_readings):
                sr = sc_readings[sc_idx]
                glucose = sr.glucose_mgdl
                activity = sr.activity_level
                
                if sr.meal_event:
                    last_meal_time = current_time
                    last_meal_carbs = sr.meal_carbs_g
                if sr.insulin_event:
                    last_insulin_time = current_time
                    last_insulin_units = sr.insulin_units
                
                in_scenario = True
                break
        
        if not in_scenario:
            # Normal glucose with circadian rhythm
            glucose = _normal_glucose(hour, patient["baseline_glucose"])
            
            # Check for meals
            is_meal, carbs, mins_since = _is_near_meal(current_time, patient["typical_meals"])
            if is_meal:
                last_meal_time = current_time
                last_meal_carbs = carbs
                # Insulin with meal
                last_insulin_time = current_time
                last_insulin_units = round(carbs / 10, 1)  # ~1u per 10g carbs
            
            # Post-meal glucose rise
            mins_post_meal = (current_time - last_meal_time).total_seconds() / 60
            if 15 < mins_post_meal < 120:
                meal_effect = last_meal_carbs * 0.5 * math.exp(-((mins_post_meal - 45) ** 2) / 2000)
                glucose += meal_effect
            
            # Insulin effect
            mins_post_insulin = (current_time - last_insulin_time).total_seconds() / 60
            if 30 < mins_post_insulin < 240:
                insulin_effect = last_insulin_units * 3 * math.exp(-((mins_post_insulin - 90) ** 2) / 5000)
                glucose -= insulin_effect
            
            glucose = round(max(40, min(300, glucose)), 1)
            activity = random.choices(
                ["rest", "light", "moderate", "high"],
                weights=[0.5, 0.3, 0.15, 0.05],
            )[0]
        
        # Compute time since last meal and insulin
        mins_since_meal = int((current_time - last_meal_time).total_seconds() / 60)
        mins_since_insulin = int((current_time - last_insulin_time).total_seconds() / 60)
        
        reading = {
            "timestamp": current_time.isoformat(),
            "glucose_mgdl": glucose,
            "glucose_trend": 0.0,  # Will be computed after
            "last_meal_mins_ago": min(mins_since_meal, 999),
            "meal_carbs_g": last_meal_carbs if mins_since_meal < 5 else 0,
            "last_insulin_units": last_insulin_units,
            "insulin_mins_ago": min(mins_since_insulin, 999),
            "activity_level": activity,
            "time_of_day": _time_of_day(hour),
            "patient_id": patient_id,
        }
        readings.append(reading)
    
    # Second pass: compute glucose trends
    for i in range(len(readings)):
        readings[i]["glucose_trend"] = _compute_glucose_trend(readings, i)
    
    return readings


def generate_all_patients(days: int = 7, output_file: str = "simulated_data.json") -> Dict:
    """Generate data for all 3 patients and save to JSON."""
    all_data = {}
    
    for patient_id in PATIENTS:
        print(f"Generating data for {patient_id} ({PATIENTS[patient_id]['name']})...")
        readings = generate_patient_data(patient_id, days=days)
        all_data[patient_id] = readings
        print(f"  → {len(readings)} readings generated")
    
    # Save to file
    with open(output_file, "w") as f:
        json.dump(all_data, f, indent=2)
    
    print(f"\nTotal readings: {sum(len(v) for v in all_data.values())}")
    print(f"Saved to {output_file}")
    
    # Also save patient profiles
    with open("patient_profiles.json", "w") as f:
        json.dump(PATIENTS, f, indent=2)
    
    return all_data


if __name__ == "__main__":
    generate_all_patients()
