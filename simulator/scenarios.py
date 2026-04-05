"""
Ayuq — Hypoglycemia Scenario Generators

Three realistic scenarios that simulate dangerous glucose patterns:
1. Post-exercise crash (glucose 140→55 over ~90 min)
2. Night-time insulin crash (glucose 120→50 during 2-4 AM)
3. Skipped meal slow drop (glucose 100→60 over ~3 hours)
"""

import math
import random
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class ScenarioReading:
    """A single generated reading within a scenario."""
    glucose_mgdl: float
    activity_level: str  # "rest", "light", "moderate", "high"
    meal_event: bool  # Whether a meal happened at this point
    meal_carbs_g: float
    insulin_event: bool  # Whether insulin was taken at this point
    insulin_units: float


def _add_noise(value: float, std: float = 3.0) -> float:
    """Add realistic biological noise to glucose readings."""
    return max(30, value + random.gauss(0, std))


def generate_post_exercise_crash(
    duration_minutes: int = 120,
    interval_minutes: int = 5,
    start_glucose: float = 145.0,
    target_low: float = 52.0,
) -> List[ScenarioReading]:
    """
    Scenario 1: Post-exercise crash.
    
    Patient exercises vigorously, causing rapid glucose consumption.
    Glucose starts around 140-150, crashes to ~55 over 90 mins,
    then slowly recovers if carbs are ingested.
    
    Timeline:
    - 0-15 min: Exercise begins, glucose rises slightly (adrenaline)
    - 15-75 min: Rapid decline as muscles consume glucose
    - 75-100 min: Dangerous low zone
    - 100-120 min: Slow recovery (body responds or carb ingested)
    """
    steps = duration_minutes // interval_minutes
    readings = []
    
    for i in range(steps):
        t = i * interval_minutes
        progress = t / duration_minutes
        
        if t <= 15:
            # Initial adrenaline spike
            glucose = start_glucose + 10 * math.sin(math.pi * t / 30)
            activity = "high"
            meal = False
            carbs = 0
            insulin = False
            insulin_u = 0
        elif t <= 75:
            # Rapid decline phase
            decline_progress = (t - 15) / 60.0
            glucose = start_glucose + 5 - (start_glucose + 5 - target_low) * (decline_progress ** 1.3)
            activity = "high" if t <= 45 else "moderate"
            meal = False
            carbs = 0
            insulin = False
            insulin_u = 0
        elif t <= 100:
            # Dangerous low zone — lingering near bottom
            glucose = target_low + random.uniform(-3, 5)
            activity = "rest"
            meal = t == 100  # Carb intake at minute 100
            carbs = 15.0 if meal else 0
            insulin = False
            insulin_u = 0
        else:
            # Slow recovery
            recovery = (t - 100) / 20.0
            glucose = target_low + 25 * recovery
            activity = "rest"
            meal = False
            carbs = 0
            insulin = False
            insulin_u = 0
        
        readings.append(ScenarioReading(
            glucose_mgdl=round(_add_noise(glucose), 1),
            activity_level=activity,
            meal_event=meal,
            meal_carbs_g=carbs,
            insulin_event=insulin,
            insulin_units=insulin_u,
        ))
    
    return readings


def generate_nighttime_insulin_crash(
    duration_minutes: int = 180,
    interval_minutes: int = 5,
    start_glucose: float = 125.0,
    target_low: float = 48.0,
) -> List[ScenarioReading]:
    """
    Scenario 2: Night-time insulin crash.
    
    Patient takes evening insulin, falls asleep. Insulin peaks during
    2-4 AM causing dangerous nocturnal hypoglycemia.
    
    Timeline:
    - 0-30 min: Post-dinner, glucose stable ~120-130
    - 30-45 min: Insulin taken, glucose starts gentle decline
    - 45-120 min: Steady decline as insulin peaks during sleep
    - 120-150 min: Dangerous low zone (2-4 AM equivalent)
    - 150-180 min: Very slow recovery as insulin wears off
    """
    steps = duration_minutes // interval_minutes
    readings = []
    
    insulin_given = False
    
    for i in range(steps):
        t = i * interval_minutes
        
        if t <= 30:
            # Stable post-dinner
            glucose = start_glucose + random.uniform(-5, 5)
            activity = "rest"
            meal = False
            carbs = 0
            insulin = (t == 30)  # Insulin at minute 30
            insulin_u = 8.0 if insulin else 0
            if insulin:
                insulin_given = True
        elif t <= 45:
            # Gentle initial decline
            decline = (t - 30) / 15.0
            glucose = start_glucose - 10 * decline
            activity = "rest"
            meal = False
            carbs = 0
            insulin = False
            insulin_u = 0
        elif t <= 120:
            # Steady decline — insulin peaking
            decline_progress = (t - 45) / 75.0
            glucose = (start_glucose - 10) - ((start_glucose - 10) - target_low) * (decline_progress ** 0.8)
            activity = "rest"
            meal = False
            carbs = 0
            insulin = False
            insulin_u = 0
        elif t <= 150:
            # Dangerous low zone
            glucose = target_low + random.uniform(-4, 6)
            activity = "rest"
            meal = False
            carbs = 0
            insulin = False
            insulin_u = 0
        else:
            # Very slow recovery
            recovery = (t - 150) / 30.0
            glucose = target_low + 15 * recovery
            activity = "rest"
            meal = False
            carbs = 0
            insulin = False
            insulin_u = 0
        
        readings.append(ScenarioReading(
            glucose_mgdl=round(_add_noise(glucose, std=2.5), 1),
            activity_level=activity,
            meal_event=meal,
            meal_carbs_g=carbs,
            insulin_event=insulin,
            insulin_units=insulin_u,
        ))
    
    return readings


def generate_skipped_meal_drop(
    duration_minutes: int = 210,
    interval_minutes: int = 5,
    start_glucose: float = 105.0,
    target_low: float = 58.0,
) -> List[ScenarioReading]:
    """
    Scenario 3: Skipped meal slow drop.
    
    Patient skips lunch, glucose gradually declines over 3+ hours.
    This is a slow, insidious drop that's harder to detect early.
    
    Timeline:
    - 0-30 min: Normal glucose, last meal wearing off
    - 30-150 min: Slow, steady decline (no meal to replenish)
    - 150-180 min: Approaching danger zone
    - 180-210 min: Low zone, eventual correction
    """
    steps = duration_minutes // interval_minutes
    readings = []
    
    for i in range(steps):
        t = i * interval_minutes
        
        if t <= 30:
            # Normal, slightly declining
            glucose = start_glucose - (t / 30.0) * 5
            activity = "light"
            meal = False
            carbs = 0
            insulin = False
            insulin_u = 0
        elif t <= 150:
            # Slow steady decline — the dangerous subtle pattern
            decline_progress = (t - 30) / 120.0
            glucose = (start_glucose - 5) - ((start_glucose - 5) - target_low) * (decline_progress ** 0.7)
            activity = "light" if t <= 90 else "rest"
            meal = False
            carbs = 0
            # Small basal insulin still active
            insulin = (t == 60)
            insulin_u = 4.0 if insulin else 0
        elif t <= 180:
            # Near danger zone
            decline_progress = (t - 150) / 30.0
            glucose = target_low + 5 - 8 * decline_progress
            activity = "rest"
            meal = False
            carbs = 0
            insulin = False
            insulin_u = 0
        else:
            # Correction (eats something)
            recovery = (t - 180) / 30.0
            glucose = target_low - 3 + 20 * recovery
            activity = "rest"
            meal = (t == 185)
            carbs = 30.0 if meal else 0
            insulin = False
            insulin_u = 0
        
        readings.append(ScenarioReading(
            glucose_mgdl=round(_add_noise(glucose, std=2.0), 1),
            activity_level=activity,
            meal_event=meal,
            meal_carbs_g=carbs,
            insulin_event=insulin,
            insulin_units=insulin_u,
        ))
    
    return readings


# Registry of all scenarios for the generator
SCENARIOS = {
    "post_exercise_crash": generate_post_exercise_crash,
    "nighttime_insulin_crash": generate_nighttime_insulin_crash,
    "skipped_meal_drop": generate_skipped_meal_drop,
}
