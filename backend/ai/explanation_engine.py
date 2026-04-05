"""
Ayuq — Explanation Engine

When risk_score > 60, calls Claude API to generate a 2-sentence explanation:
  1. Why risk is high (citing specific factors)
  2. What action to take

Includes graceful fallback if API key is not set or call fails.
"""

import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ExplanationEngine:
    """
    Generates natural language explanations for high-risk alerts
    using Claude (Anthropic) API.
    """
    
    RISK_THRESHOLD = 60  # Only generate explanations above this score
    
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._client = None
        
        if self.api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
                logger.info("✓ Claude API initialized for explanation engine")
            except ImportError:
                logger.warning("anthropic package not installed — using fallback explanations")
            except Exception as e:
                logger.warning(f"Claude API init failed: {e} — using fallback explanations")
        else:
            logger.info("No ANTHROPIC_API_KEY set — using rule-based fallback explanations")
    
    def _build_prompt(self, reading: Dict, features: Dict, risk_result: Dict) -> str:
        """Build the structured prompt for Claude."""
        glucose = reading.get("glucose_mgdl", 0)
        trend = features.get("glucose_trend_computed", 0)
        risk_score = risk_result.get("risk_score", 0)
        risk_level = risk_result.get("risk_level", "HIGH")
        time_to_event = risk_result.get("predicted_time_to_event")
        factors = risk_result.get("contributing_factors", [])
        meal_gap = features.get("meal_gap", {}).get("meal_gap_minutes", 0)
        insulin = features.get("insulin_activity", {})
        activity = reading.get("activity_level", "rest")
        time_of_day = reading.get("time_of_day", "morning")
        
        prompt = f"""You are a clinical decision support AI assistant for diabetes management.
A patient is showing elevated hypoglycemia risk. Generate a brief, actionable explanation.

PATIENT DATA:
- Current glucose: {glucose:.0f} mg/dL
- Glucose trend: {trend:+.1f} mg/dL per 5 minutes ({"dropping" if trend < 0 else "rising" if trend > 0 else "stable"})
- Risk score: {risk_score:.0f}/100 ({risk_level})
- Estimated time to hypoglycemia: {f"{time_to_event:.0f} minutes" if time_to_event else "N/A"}
- Minutes since last meal: {meal_gap}
- Insulin status: {insulin.get("insulin_phase", "none")} phase, {insulin.get("insulin_activity_pct", 0):.0f}% activity
- Activity level: {activity}
- Time of day: {time_of_day}

KEY RISK FACTORS:
{chr(10).join(f"- {f}" for f in factors[:4])}

INSTRUCTIONS:
Generate EXACTLY 2 sentences:
1. First sentence: Explain WHY the risk is elevated, referencing the specific data points.
2. Second sentence: Recommend ONE immediate action the patient should take.

Keep the language clear, calm, and clinical. Do NOT use medical jargon unnecessarily.
Do NOT add any prefix, header, or bullet points — just the 2 sentences."""
        
        return prompt
    
    def _generate_fallback(self, reading: Dict, features: Dict, risk_result: Dict) -> str:
        """Generate a rule-based fallback explanation when Claude is unavailable."""
        glucose = reading.get("glucose_mgdl", 0)
        trend = features.get("glucose_trend_computed", 0)
        time_to_event = risk_result.get("predicted_time_to_event")
        factors = risk_result.get("contributing_factors", [])
        flags = features.get("contextual_flags", [])
        
        # Build the WHY sentence
        why_parts = []
        if glucose < 80:
            why_parts.append(f"glucose is low at {glucose:.0f} mg/dL")
        if trend < -2:
            why_parts.append(f"dropping at {abs(trend):.1f} mg/dL per 5 minutes")
        elif trend < -1:
            why_parts.append(f"in a declining trend")
        
        if "nighttime_insulin_risk" in flags:
            why_parts.append("during nighttime with active insulin")
        elif "post_exercise_risk" in flags:
            why_parts.append("following physical activity")
        elif "fasting_risk" in flags:
            why_parts.append("with an extended fasting period")
        
        if time_to_event and time_to_event < 60:
            why_parts.append(f"with projected hypoglycemia in ~{time_to_event:.0f} minutes")
        
        why = "Your glucose " + " and ".join(why_parts[:3]) if why_parts else \
              f"Multiple risk factors are converging — glucose at {glucose:.0f} mg/dL with a declining trend"
        why += "."
        
        # Build the ACTION sentence
        if glucose < 60:
            action = "Consume 15-20g of fast-acting carbohydrates immediately (glucose tabs, juice, or regular soda) and recheck in 15 minutes."
        elif glucose < 75:
            action = "Consider having a small snack with 15g of carbohydrates to prevent further decline."
        elif trend < -3:
            action = "Have a carbohydrate snack soon and avoid strenuous activity until levels stabilize."
        elif "nighttime_insulin_risk" in flags:
            action = "Set an alarm to recheck glucose in 30 minutes and keep fast-acting carbs at bedside."
        else:
            action = "Monitor closely over the next 15-30 minutes and prepare a snack if the decline continues."
        
        return f"{why} {action}"
    
    async def generate_explanation(
        self,
        reading: Dict,
        features: Dict,
        risk_result: Dict,
    ) -> Optional[str]:
        """
        Generate an explanation for a high-risk alert.
        
        Returns None if risk is below threshold.
        Uses Claude API if available, falls back to rules otherwise.
        """
        risk_score = risk_result.get("risk_score", 0)
        
        if risk_score < self.RISK_THRESHOLD:
            return None
        
        # Try Claude API first
        if self._client:
            try:
                prompt = self._build_prompt(reading, features, risk_result)
                
                message = self._client.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=200,
                    messages=[{"role": "user", "content": prompt}],
                )
                
                explanation = message.content[0].text.strip()
                logger.info(f"Claude explanation generated for risk {risk_score:.0f}")
                return explanation
                
            except Exception as e:
                logger.warning(f"Claude API call failed: {e} — using fallback")
        
        # Fallback to rule-based
        return self._generate_fallback(reading, features, risk_result)
    
    def generate_explanation_sync(
        self,
        reading: Dict,
        features: Dict,
        risk_result: Dict,
    ) -> Optional[str]:
        """Synchronous version for non-async contexts."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context — can't nest
                return self._generate_fallback(reading, features, risk_result)
            return loop.run_until_complete(
                self.generate_explanation(reading, features, risk_result)
            )
        except RuntimeError:
            return self._generate_fallback(reading, features, risk_result)
