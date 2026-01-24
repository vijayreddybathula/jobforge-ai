"""Decision engine service."""

from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from packages.database.models import JobScore, Application, JobRaw
from packages.database.connection import get_db
from packages.common.redis_cache import get_redis_cache
from packages.common.logging import get_logger

logger = get_logger(__name__)


class DecisionService:
    """Service for making apply/validate/skip decisions."""
    
    def __init__(self):
        """Initialize decision service."""
        self.cache = get_redis_cache()
        self.cooldown_days = 30
        self.max_applications_per_month = 10
    
    def make_decision(
        self,
        job_id: UUID,
        user_id: UUID,
        score: int,
        verdict: str,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Make final decision for job application.
        
        Args:
            job_id: Job ID
            user_id: User ID
            score: Fit score
            verdict: Initial verdict from scoring
            db: Database session
        
        Returns:
            Decision dictionary
        """
        if db is None:
            db = next(get_db())
        
        # Get job to check company
        job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
        if not job:
            return {
                "decision": "SKIP",
                "reason": "Job not found"
            }
        
        company = job.company or "unknown"
        
        # Check company cooldown
        if self._check_cooldown(user_id, company):
            return {
                "decision": "SKIP",
                "reason": f"Cooldown period active for {company}"
            }
        
        # Check application limits
        if self._check_application_limit(user_id, company):
            return {
                "decision": "SKIP",
                "reason": f"Monthly application limit reached for {company}"
            }
        
        # Apply decision rules based on score
        if score < 50:
            final_decision = "SKIP"
        elif score < 70:
            final_decision = "VALIDATE"
        elif score < 85:
            final_decision = "ASSISTED_APPLY"
        else:
            # Check if auto-submit is eligible
            if self._is_auto_submit_eligible(job, verdict):
                final_decision = "ELIGIBLE_AUTO_SUBMIT"
            else:
                final_decision = "ASSISTED_APPLY"
        
        return {
            "decision": final_decision,
            "score": score,
            "verdict": verdict,
            "reason": self._get_decision_reason(final_decision, score)
        }
    
    def _check_cooldown(self, user_id: UUID, company: str) -> bool:
        """Check if company cooldown is active."""
        cooldown_key = f"cooldown:{user_id}:{company.lower()}"
        
        if not self.cache._is_available():
            return False
        
        # Check if cooldown exists
        if self.cache.exists(cooldown_key):
            return True
        
        return False
    
    def _set_cooldown(self, user_id: UUID, company: str) -> None:
        """Set company cooldown."""
        cooldown_key = f"cooldown:{user_id}:{company.lower()}"
        cooldown_seconds = self.cooldown_days * 24 * 60 * 60
        self.cache.set(cooldown_key, True, ttl=cooldown_seconds)
    
    def _check_application_limit(self, user_id: UUID, company: str) -> bool:
        """Check if monthly application limit reached."""
        limit_key = f"app_limit:{user_id}:{company.lower()}:{datetime.utcnow().strftime('%Y-%m')}"
        
        if not self.cache._is_available():
            return False
        
        current_count = self.cache.get(limit_key)
        if current_count is None:
            current_count = 0
        else:
            current_count = int(current_count)
        
        return current_count >= self.max_applications_per_month
    
    def _increment_application_count(self, user_id: UUID, company: str) -> None:
        """Increment application count for company."""
        limit_key = f"app_limit:{user_id}:{company.lower()}:{datetime.utcnow().strftime('%Y-%m')}"
        self.cache.increment(limit_key, 1)
        # Set expiration to end of month
        days_until_month_end = (datetime.utcnow().replace(day=28) + timedelta(days=4)).replace(day=1) - datetime.utcnow()
        self.cache.client.expire(limit_key, int(days_until_month_end.total_seconds()))
    
    def _is_auto_submit_eligible(self, job: JobRaw, verdict: str) -> bool:
        """Check if job is eligible for auto-submit."""
        # Only for certain platforms
        eligible_sources = ["greenhouse", "lever"]
        if job.source.lower() not in eligible_sources:
            return False
        
        # Verdict must be ELIGIBLE_AUTO_SUBMIT
        if verdict != "ELIGIBLE_AUTO_SUBMIT":
            return False
        
        return True
    
    def _get_decision_reason(self, decision: str, score: int) -> str:
        """Get human-readable reason for decision."""
        reasons = {
            "SKIP": f"Low fit score ({score}/100). Not recommended for application.",
            "VALIDATE": f"Moderate fit score ({score}/100). Review before applying.",
            "ASSISTED_APPLY": f"Good fit score ({score}/100). Recommended for application with review.",
            "ELIGIBLE_AUTO_SUBMIT": f"Excellent fit score ({score}/100). Eligible for auto-submit (if enabled)."
        }
        return reasons.get(decision, "Unknown decision")
