"""Auto-submit gating logic."""

from typing import Dict, Any
from packages.database.models import JobRaw, JobScore
from packages.common.logging import get_logger

logger = get_logger(__name__)


class AutoSubmitGate:
    """Gate for auto-submit eligibility."""
    
    def is_eligible(
        self,
        job: JobRaw,
        score: JobScore,
        platform: str
    ):
        """Check if job is eligible for auto-submit.
        
        Args:
            job: Job record
            score: Job score
            platform: Application platform
        
        Returns:
            Tuple of (is_eligible, reason)
        """
        # Score must be >= 85
        if score.total_score < 85:
            return False, f"Score {score.total_score} is below auto-submit threshold (85)"
        
        # Platform must be reliable
        eligible_platforms = ["greenhouse", "lever"]
        if platform.lower() not in eligible_platforms:
            return False, f"Platform {platform} is not eligible for auto-submit"
        
        # Verdict must be ELIGIBLE_AUTO_SUBMIT
        if score.verdict != "ELIGIBLE_AUTO_SUBMIT":
            return False, f"Verdict {score.verdict} is not eligible for auto-submit"
        
        return True, "Eligible for auto-submit"
