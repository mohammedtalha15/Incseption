"""
Ayuq — Risk Engine

Rule-based scoring system that computes hypoglycemia risk (0-100)
from enriched features. Designed to be replaceable with ML models.

Scoring Weights:
    Glucose Level:  25%  (current absolute level)
    Glucose Trend:  35%  (MOST IMPORTANT — rate of change)
    Insulin Recency: 15%  (active insulin window)
    Meal Gap:       10%  (time since last meal)
    Time of Day:    10%  (nocturnal risk)
    Activity Level:  5%  (exercise-induced risk)
"""

from typing import Dict, List, Optional, Tuple


class RiskEngine:
    """
    Rule-based hypoglycemia risk scoring engine.
    
    Architecture designed for easy replacement:
    - Subclass and override `score()` for ML models
    - All inputs/outputs use standard dicts
    """
    
    # Weight configuration (must sum to 100)
    WEIGHTS = {
        "glucose_level": 25,
        "glucose_trend": 35,
        "insulin_recency": 15,
        "meal_gap": 10,
        "time_of_day": 10,
        "activity_level": 5,
    }
    
    def score_glucose_level(self, glucose: float) -> Tuple[float, str]:
        """
        Score based on absolute glucose level.
        Returns (score 0-100, reason string).
        """
        if glucose < 54:
            return 100, f"Severe low: {glucose:.0f} mg/dL (critical <54)"
        elif glucose < 60:
            return 90, f"Very low: {glucose:.0f} mg/dL (<60)"
        elif glucose < 70:
            return 75, f"Low: {glucose:.0f} mg/dL (below threshold)"
        elif glucose < 80:
            return 50, f"Near-low: {glucose:.0f} mg/dL (approaching threshold)"
        elif glucose < 90:
            return 30, f"Low-normal: {glucose:.0f} mg/dL"
        elif glucose < 120:
            return 5, f"Normal: {glucose:.0f} mg/dL"
        elif glucose < 180:
            return 0, f"Elevated: {glucose:.0f} mg/dL (no hypo risk)"
        else:
            return 0, f"High: {glucose:.0f} mg/dL (no hypo risk)"
    
    def score_glucose_trend(self, trend: float, glucose: float) -> Tuple[float, str]:
        """
        Score based on glucose rate of change.
        THIS IS THE MOST IMPORTANT FACTOR — a fast-dropping glucose
        is dangerous even from normal levels.
        
        trend: mg/dL per 5 minutes (negative = dropping)
        """
        if trend < -4:
            score = 100
            reason = f"Plummeting: {trend:+.1f} mg/dL/5min (critical drop)"
        elif trend < -3:
            score = 85
            reason = f"Rapidly falling: {trend:+.1f} mg/dL/5min"
        elif trend < -2:
            score = 65
            reason = f"Falling fast: {trend:+.1f} mg/dL/5min"
        elif trend < -1:
            score = 40
            reason = f"Declining: {trend:+.1f} mg/dL/5min"
        elif trend < -0.5:
            score = 20
            reason = f"Slight decline: {trend:+.1f} mg/dL/5min"
        elif trend <= 0.5:
            score = 5
            reason = f"Stable: {trend:+.1f} mg/dL/5min"
        else:
            score = 0
            reason = f"Rising: {trend:+.1f} mg/dL/5min (no hypo risk)"
        
        # Amplify if already low
        if glucose < 90 and trend < -1:
            score = min(100, score * 1.3)
            reason += " [amplified: already near threshold]"
        
        return round(score, 1), reason
    
    def score_insulin_recency(self, insulin_activity: Dict) -> Tuple[float, str]:
        """Score based on insulin activity window."""
        activity_pct = insulin_activity.get("insulin_activity_pct", 0)
        phase = insulin_activity.get("insulin_phase", "none")
        is_active = insulin_activity.get("insulin_active", False)
        
        if not is_active:
            return 0, "No active insulin"
        
        if phase == "peak":
            score = 85
            reason = f"Insulin peaking ({activity_pct:.0f}% activity)"
        elif phase == "rising":
            score = 60
            reason = f"Insulin rising ({activity_pct:.0f}% activity)"
        elif phase == "declining":
            score = 30
            reason = f"Insulin declining ({activity_pct:.0f}% activity)"
        elif phase == "onset":
            score = 20
            reason = f"Insulin onset ({activity_pct:.0f}% activity)"
        else:
            score = 10
            reason = f"Insulin tail ({activity_pct:.0f}% activity)"
        
        return score, reason
    
    def score_meal_gap(self, meal_gap: Dict) -> Tuple[float, str]:
        """Score based on time since last meal."""
        gap_mins = meal_gap.get("meal_gap_minutes", 0)
        gap_level = meal_gap.get("meal_gap_level", "recent")
        
        if gap_level == "prolonged":
            return 90, f"Prolonged fast: {gap_mins} min since last meal"
        elif gap_level == "extended":
            return 65, f"Extended gap: {gap_mins} min since last meal"
        elif gap_level == "moderate":
            return 35, f"Moderate gap: {gap_mins} min since last meal"
        else:
            return 5, f"Recent meal: {gap_mins} min ago"
    
    def score_time_of_day(self, time_of_day: str) -> Tuple[float, str]:
        """Score based on time of day (nocturnal risk amplification)."""
        if time_of_day == "night":
            return 80, "Nighttime: reduced counter-regulatory response, unaware"
        elif time_of_day == "morning":
            return 20, "Morning: dawn phenomenon may protect"
        elif time_of_day == "evening":
            return 30, "Evening: transitioning to higher-risk period"
        else:
            return 5, "Daytime: lower risk period"
    
    def score_activity_level(self, activity: str, trend: float) -> Tuple[float, str]:
        """Score based on recent physical activity."""
        if activity == "high":
            score = 80
            reason = "High activity: rapid glucose consumption"
            if trend < -2:
                score = 95
                reason += " + fast drop"
        elif activity == "moderate":
            score = 45
            reason = "Moderate activity: increased glucose usage"
        elif activity == "light":
            score = 15
            reason = "Light activity"
        else:
            score = 0
            reason = "At rest"
        
        return score, reason
    
    def predict_time_to_event(self, glucose: float, trend: float) -> Optional[float]:
        """
        Estimate minutes until glucose reaches 70 mg/dL (hypo threshold).
        
        Returns None if glucose is rising or already below threshold.
        """
        if glucose <= 70:
            return 0  # Already in hypo
        
        if trend >= 0:
            return None  # Not dropping
        
        # Simple linear extrapolation
        # trend is mg/dL per 5 min interval
        # Time to reach 70 = (current - 70) / |trend| * 5 minutes
        delta = glucose - 70
        rate_per_min = abs(trend) / 5.0
        
        if rate_per_min < 0.01:
            return None  # Effectively stable
        
        time_mins = delta / rate_per_min
        
        # Cap at 6 hours
        return round(min(time_mins, 360), 1)
    
    def score(self, reading: Dict, features: Dict) -> Dict:
        """
        Main scoring function.
        
        Args:
            reading: Raw reading dict
            features: Output from FeatureBuilder.build_features()
            
        Returns:
            Dict with risk_score, risk_level, predicted_time_to_event,
            contributing_factors, and component scores.
        """
        glucose = reading["glucose_mgdl"]
        trend = features.get("glucose_trend_computed", reading.get("glucose_trend", 0))
        insulin_activity = features.get("insulin_activity", {})
        meal_gap = features.get("meal_gap", {})
        time_of_day = reading.get("time_of_day", "morning")
        activity = reading.get("activity_level", "rest")
        
        # Score each component
        glucose_score, glucose_reason = self.score_glucose_level(glucose)
        trend_score, trend_reason = self.score_glucose_trend(trend, glucose)
        insulin_score, insulin_reason = self.score_insulin_recency(insulin_activity)
        meal_score, meal_reason = self.score_meal_gap(meal_gap)
        tod_score, tod_reason = self.score_time_of_day(time_of_day)
        activity_score, activity_reason = self.score_activity_level(activity, trend)
        
        # Weighted total
        risk_score = (
            glucose_score * self.WEIGHTS["glucose_level"] / 100 +
            trend_score * self.WEIGHTS["glucose_trend"] / 100 +
            insulin_score * self.WEIGHTS["insulin_recency"] / 100 +
            meal_score * self.WEIGHTS["meal_gap"] / 100 +
            tod_score * self.WEIGHTS["time_of_day"] / 100 +
            activity_score * self.WEIGHTS["activity_level"] / 100
        )
        
        risk_score = round(min(100, max(0, risk_score)), 1)
        
        # Determine risk level
        if risk_score >= 60:
            risk_level = "HIGH"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        # Predict time to event
        predicted_time = self.predict_time_to_event(glucose, trend)
        
        # Compile contributing factors (sorted by impact)
        factors_with_scores = [
            (trend_score * self.WEIGHTS["glucose_trend"] / 100, trend_reason),
            (glucose_score * self.WEIGHTS["glucose_level"] / 100, glucose_reason),
            (insulin_score * self.WEIGHTS["insulin_recency"] / 100, insulin_reason),
            (meal_score * self.WEIGHTS["meal_gap"] / 100, meal_reason),
            (tod_score * self.WEIGHTS["time_of_day"] / 100, tod_reason),
            (activity_score * self.WEIGHTS["activity_level"] / 100, activity_reason),
        ]
        factors_with_scores.sort(key=lambda x: x[0], reverse=True)
        
        # Only include factors contributing > 2 points
        contributing_factors = [
            reason for score, reason in factors_with_scores if score > 2
        ]
        
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "predicted_time_to_event": predicted_time,
            "contributing_factors": contributing_factors,
            "component_scores": {
                "glucose_level": round(glucose_score * self.WEIGHTS["glucose_level"] / 100, 1),
                "glucose_trend": round(trend_score * self.WEIGHTS["glucose_trend"] / 100, 1),
                "insulin_recency": round(insulin_score * self.WEIGHTS["insulin_recency"] / 100, 1),
                "meal_gap": round(meal_score * self.WEIGHTS["meal_gap"] / 100, 1),
                "time_of_day": round(tod_score * self.WEIGHTS["time_of_day"] / 100, 1),
                "activity_level": round(activity_score * self.WEIGHTS["activity_level"] / 100, 1),
            },
        }
