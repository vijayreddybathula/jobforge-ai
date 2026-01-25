"""Rules engine for hard constraint checking."""

from typing import Dict, Any, Optional
from packages.database.models import UserPreferences
from packages.schemas.jd_schema import ParsedJD
from packages.common.logging import get_logger

logger = get_logger(__name__)


class RulesEngine:
    """Engine for checking hard constraints before scoring."""

    def check_constraints(self, parsed_jd: ParsedJD, user_preferences: UserPreferences):
        """Check hard constraints.

        Args:
            parsed_jd: Parsed job description
            user_preferences: User preferences

        Returns:
            Tuple of (is_allowed, rejection_reason)
        """
        # Check visa requirements
        if parsed_jd.red_flags:
            for flag in parsed_jd.red_flags:
                if "citizenship" in flag.lower() or "security clearance" in flag.lower():
                    if (
                        user_preferences.visa_status
                        and "citizen" not in user_preferences.visa_status.lower()
                    ):
                        return (
                            False,
                            f"Job requires {flag} but user visa status is {user_preferences.visa_status}",
                        )

        # Check location constraints
        if user_preferences.location_preferences:
            loc_prefs = user_preferences.location_preferences
            if isinstance(loc_prefs, dict):
                remote_only = loc_prefs.get("remote_only", False)
                if remote_only and parsed_jd.location_type.value not in ["Remote", "Unknown"]:
                    return False, "User requires remote but job is not remote"

        # Check salary floor
        if user_preferences.salary_min_usd and parsed_jd.salary_range:
            if (
                parsed_jd.salary_range.max
                and parsed_jd.salary_range.max < user_preferences.salary_min_usd
            ):
                return (
                    False,
                    f"Job max salary ${parsed_jd.salary_range.max} is below user minimum ${user_preferences.salary_min_usd}",
                )

        # All constraints passed
        return True, None
