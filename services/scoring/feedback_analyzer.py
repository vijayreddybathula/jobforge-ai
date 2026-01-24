"""Feedback analyzer for improving scoring."""

from typing import Dict, Any, List
from sqlalchemy.orm import Session
from packages.database.models import JobScore, Outcome, Application
from packages.database.connection import get_db
from packages.common.logging import get_logger

logger = get_logger(__name__)


class FeedbackAnalyzer:
    """Analyze outcomes to improve scoring."""
    
    def analyze_feedback(self, user_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Analyze feedback and outcomes.
        
        Args:
            user_id: User ID
            db: Database session
        
        Returns:
            Analysis results
        """
        if db is None:
            db = next(get_db())
        
        # Get all applications with outcomes
        applications = db.query(Application).filter(
            Application.user_id == user_id
        ).all()
        
        # Group by score bands
        score_bands = {
            "0-49": {"total": 0, "phone_screen": 0, "onsite": 0, "offer": 0},
            "50-69": {"total": 0, "phone_screen": 0, "onsite": 0, "offer": 0},
            "70-84": {"total": 0, "phone_screen": 0, "onsite": 0, "offer": 0},
            "85-100": {"total": 0, "phone_screen": 0, "onsite": 0, "offer": 0},
        }
        
        for app in applications:
            score = db.query(JobScore).filter(
                JobScore.job_id == app.job_id,
                JobScore.user_id == app.user_id
            ).first()
            
            if not score:
                continue
            
            # Determine score band
            if score.total_score < 50:
                band = "0-49"
            elif score.total_score < 70:
                band = "50-69"
            elif score.total_score < 85:
                band = "70-84"
            else:
                band = "85-100"
            
            score_bands[band]["total"] += 1
            
            # Get outcomes
            outcomes = db.query(Outcome).filter(
                Outcome.application_id == app.application_id
            ).all()
            
            for outcome in outcomes:
                if outcome.stage == "phone_screen":
                    score_bands[band]["phone_screen"] += 1
                elif outcome.stage == "onsite":
                    score_bands[band]["onsite"] += 1
                elif outcome.stage == "offer":
                    score_bands[band]["offer"] += 1
        
        # Calculate callback rates
        analysis = {}
        for band, data in score_bands.items():
            if data["total"] > 0:
                callback_rate = (data["phone_screen"] + data["onsite"] + data["offer"]) / data["total"]
                analysis[band] = {
                    **data,
                    "callback_rate": round(callback_rate * 100, 2)
                }
            else:
                analysis[band] = data
        
        logger.info(f"Feedback analysis completed for user {user_id}")
        
        return {
            "user_id": user_id,
            "score_bands": analysis,
            "recommendations": self._generate_recommendations(analysis)
        }
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        # Check callback rates
        for band, data in analysis.items():
            if isinstance(data, dict) and data.get("total", 0) > 5:
                callback_rate = data.get("callback_rate", 0)
                if callback_rate < 20 and band in ["70-84", "85-100"]:
                    recommendations.append(
                        f"Low callback rate ({callback_rate}%) for {band} score band. "
                        "Consider adjusting scoring weights or improving artifact quality."
                    )
        
        return recommendations
