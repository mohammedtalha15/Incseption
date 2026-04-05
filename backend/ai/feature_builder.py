"""
Ayuq — Feature Builder

Computes derived features from raw CGM readings for the risk engine.
Features include glucose trend, insulin activity window, meal gap analysis,
and contextual flags.
"""

from datetime import datetime
from typing import Dict, List, Optional


class FeatureBuilder:
    """
    Transforms raw readings into enriched feature vectors.
    
    Maintains a rolling window of recent readings per patient for
    trend computation and pattern detection.
    """
    
    def __init__(self, window_size: int = 12):
        """
        Args:
            window_size: Number of recent readings to keep per patient
                         (12 readings × 5 min = 1 hour of history)
        """
        self.window_size = window_size
        self._history: Dict[str, List[Dict]] = {}
    
    def _get_history(self, patient_id: str) -> List[Dict]:
        """Get the reading history for a patient."""
        if patient_id not in self._history:
            self._history[patient_id] = []
        return self._history[patient_id]
    
    def _add_to_history(self, patient_id: str, reading: Dict):
        """Add a reading to the patient's rolling window."""
        history = self._get_history(patient_id)
        history.append(reading)
        if len(history) > self.window_size:
            history.pop(0)
    
    def compute_glucose_trend(self, patient_id: str, current_glucose: float) -> float:
        """
        Compute glucose rate of change (mg/dL per 5 minutes).
        
        Uses weighted linear regression over last 3-5 readings,
        with more recent readings weighted higher.
        
        Returns:
            Negative = dropping, Positive = rising, ~0 = stable
        """
        history = self._get_history(patient_id)
        
        if len(history) < 2:
            return 0.0
        
        # Take up to last 5 readings
        recent = history[-5:]
        
        # Weighted differences (more recent = higher weight)
        weighted_sum = 0.0
        weight_total = 0.0
        
        for i in range(1, len(recent)):
            delta = recent[i].get("glucose_mgdl", 0) - recent[i-1].get("glucose_mgdl", 0)
            weight = i  # More recent = higher weight
            weighted_sum += delta * weight
            weight_total += weight
        
        if weight_total == 0:
            return 0.0
        
        return round(weighted_sum / weight_total, 2)
    
    def compute_insulin_activity(self, insulin_mins_ago: int, insulin_units: float) -> Dict:
        """
        Compute insulin activity window.
        
        Insulin action profile (rapid-acting):
        - Onset: 10-15 minutes
        - Peak: 60-90 minutes
        - Duration: 3-4 hours (180-240 min)
        
        Returns dict with activity level and flags.
        """
        if insulin_units <= 0 or insulin_mins_ago > 300:
            return {
                "insulin_active": False,
                "insulin_phase": "none",
                "insulin_activity_pct": 0.0,
            }
        
        # Model insulin as a skewed bell curve
        if insulin_mins_ago < 15:
            phase = "onset"
            activity = 0.1 + 0.3 * (insulin_mins_ago / 15.0)
        elif insulin_mins_ago < 60:
            phase = "rising"
            activity = 0.4 + 0.5 * ((insulin_mins_ago - 15) / 45.0)
        elif insulin_mins_ago < 120:
            phase = "peak"
            activity = 0.9 + 0.1 * (1 - abs(insulin_mins_ago - 75) / 45.0)
        elif insulin_mins_ago < 240:
            phase = "declining"
            activity = 0.9 * (1 - (insulin_mins_ago - 120) / 120.0)
        else:
            phase = "tail"
            activity = max(0, 0.1 * (1 - (insulin_mins_ago - 240) / 60.0))
        
        return {
            "insulin_active": activity > 0.1,
            "insulin_phase": phase,
            "insulin_activity_pct": round(min(1.0, max(0, activity)) * 100, 1),
        }
    
    def compute_meal_gap(self, last_meal_mins_ago: int) -> Dict:
        """
        Analyze time since last meal.
        
        Significant gaps:
        - >2h: glucose support weakening
        - >3h: notable gap
        - >4h: high risk of glucose depletion
        """
        if last_meal_mins_ago < 120:
            gap_level = "recent"
            gap_risk = "low"
        elif last_meal_mins_ago < 180:
            gap_level = "moderate"
            gap_risk = "moderate"
        elif last_meal_mins_ago < 240:
            gap_level = "extended"
            gap_risk = "elevated"
        else:
            gap_level = "prolonged"
            gap_risk = "high"
        
        return {
            "meal_gap_minutes": last_meal_mins_ago,
            "meal_gap_level": gap_level,
            "meal_gap_risk": gap_risk,
        }
    
    def compute_contextual_flags(
        self,
        patient_id: str,
        glucose: float,
        trend: float,
        activity: str,
        time_of_day: str,
        insulin_activity: Dict,
        meal_gap: Dict,
    ) -> List[str]:
        """
        Generate contextual warning flags combining multiple signals.
        """
        flags = []
        
        # Trend flags
        if trend < -3:
            flags.append("rapid_glucose_drop")
        elif trend < -1:
            flags.append("moderate_glucose_decline")
        elif trend > 3:
            flags.append("rapid_glucose_rise")
        
        # Level flags
        if glucose < 54:
            flags.append("severe_hypoglycemia")
        elif glucose < 70:
            flags.append("hypoglycemia")
        elif glucose < 80:
            flags.append("near_hypo_threshold")
        elif glucose > 250:
            flags.append("severe_hyperglycemia")
        elif glucose > 180:
            flags.append("hyperglycemia")
        
        # Context flags
        if activity in ("high", "moderate") and trend < -1:
            flags.append("post_exercise_risk")
        
        if time_of_day == "night" and insulin_activity.get("insulin_active"):
            flags.append("nighttime_insulin_risk")
        
        if meal_gap["meal_gap_level"] in ("extended", "prolonged"):
            flags.append("fasting_risk")
        
        if (
            insulin_activity.get("insulin_phase") in ("peak", "rising")
            and glucose < 100
        ):
            flags.append("insulin_peak_with_low_glucose")
        
        # Compound risk: multiple factors combining
        risk_count = sum([
            trend < -2,
            glucose < 90,
            insulin_activity.get("insulin_active", False),
            meal_gap["meal_gap_level"] in ("extended", "prolonged"),
        ])
        if risk_count >= 3:
            flags.append("compound_risk")
        
        return flags
    
    def build_features(self, reading: Dict) -> Dict:
        """
        Main entry point: take a raw reading and produce enriched features.
        
        Args:
            reading: Raw reading dict with the standard schema
            
        Returns:
            Dict of computed features
        """
        patient_id = reading["patient_id"]
        glucose = reading["glucose_mgdl"]
        
        # 1. Glucose trend (rate of change)
        trend = self.compute_glucose_trend(patient_id, glucose)
        
        # Use provided trend if our history is insufficient
        if len(self._get_history(patient_id)) < 3 and reading.get("glucose_trend", 0) != 0:
            trend = reading["glucose_trend"]
        
        # 2. Insulin activity window
        insulin_activity = self.compute_insulin_activity(
            reading.get("insulin_mins_ago", 999),
            reading.get("last_insulin_units", 0),
        )
        
        # 3. Meal gap analysis
        meal_gap = self.compute_meal_gap(
            reading.get("last_meal_mins_ago", 999),
        )
        
        # 4. Contextual flags
        flags = self.compute_contextual_flags(
            patient_id=patient_id,
            glucose=glucose,
            trend=trend,
            activity=reading.get("activity_level", "rest"),
            time_of_day=reading.get("time_of_day", "morning"),
            insulin_activity=insulin_activity,
            meal_gap=meal_gap,
        )
        
        # Add to history for future trend calculations
        self._add_to_history(patient_id, reading)
        
        features = {
            "glucose_trend_computed": trend,
            "insulin_activity": insulin_activity,
            "meal_gap": meal_gap,
            "contextual_flags": flags,
            "history_depth": len(self._get_history(patient_id)),
        }
        
        return features
