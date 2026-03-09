"""Auto-submit gate — hard rules before any automated submission."""

from typing import Tuple, Optional, Any
from packages.common.logging import get_logger

logger = get_logger(__name__)

AUTO_SUBMIT_MIN_SCORE = 85
AUTO_SUBMIT_ALLOWED_PLATFORMS = ["greenhouse", "lever"]
MAX_APPLICATIONS_PER_COMPANY_PER_MONTH = 2


class AutoSubmitGate:
    """Enforce hard constraints before allowing automated job submission."""

    def check(
        self,
        score: int,
        verdict: str,
        job_url: str,
        user_preferences: Optional[Any] = None,
    ) -> Tuple[bool, str]:
        """
        Returns (can_auto_submit, reason).
        All conditions must pass for auto-submit to be eligible.
        In practice, we always stop_before_submit=True — this is for future use.
        """
        # 1. Score threshold
        if score < AUTO_SUBMIT_MIN_SCORE:
            return False, f"Score {score} below auto-submit threshold of {AUTO_SUBMIT_MIN_SCORE}"

        # 2. Verdict must be ELIGIBLE_AUTO_SUBMIT
        if verdict != "ELIGIBLE_AUTO_SUBMIT":
            return False, f"Verdict '{verdict}' not eligible for auto-submit"

        # 3. Platform must be Greenhouse or Lever (not LinkedIn/generic)
        platform = self._detect_platform(job_url)
        if platform not in AUTO_SUBMIT_ALLOWED_PLATFORMS:
            return False, f"Platform '{platform}' not supported for auto-submit (only {AUTO_SUBMIT_ALLOWED_PLATFORMS})"

        logger.info(f"Auto-submit gate PASSED: score={score}, verdict={verdict}, platform={platform}")
        return True, "All auto-submit conditions met"

    def _detect_platform(self, url: str) -> str:
        url_lower = url.lower()
        if "greenhouse" in url_lower:
            return "greenhouse"
        elif "lever" in url_lower:
            return "lever"
        elif "linkedin" in url_lower:
            return "linkedin"
        else:
            return "generic"
