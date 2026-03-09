"""Rules engine for hard constraint checking."""

from packages.database.models import UserPreferences
from packages.schemas.jd_schema import ParsedJD
from packages.common.logging import get_logger

logger = get_logger(__name__)

# Salary values below this are almost certainly bad parses.
MIN_CREDIBLE_SALARY = 10_000


class RulesEngine:
    """Engine for checking hard constraints before scoring."""

    def check_constraints(self, parsed_jd: ParsedJD, user_preferences: UserPreferences):
        """
        Returns (is_allowed: bool, rejection_reason: str | None).
        Only rejects when CONFIDENT the job fails a hard constraint.
        """

        # ── Visa / citizenship ────────────────────────────────────────────────
        if parsed_jd.red_flags:
            for flag in parsed_jd.red_flags:
                fl = flag.lower()
                if "citizenship" in fl or "security clearance" in fl:
                    if (
                        user_preferences.visa_status
                        and "citizen" not in user_preferences.visa_status.lower()
                    ):
                        return False, f"Job requires {flag} but your visa status is {user_preferences.visa_status}"

        # ── Location (remote-only hard constraint) ────────────────────────────
        # Reads the correct key saved by PreferencesPage: 'remote' not 'remote_only'.
        # Only hard-rejects if user explicitly wants remote-only (remote=True AND
        # hybrid=False AND onsite=False) and the job is definitely onsite.
        if user_preferences.location_preferences:
            loc = user_preferences.location_preferences
            if isinstance(loc, dict):
                remote_ok = loc.get("remote", False)
                hybrid_ok = loc.get("hybrid", False)
                onsite_ok = loc.get("onsite", False)
                # Only hard-reject if user is remote-only AND job is confirmed onsite
                user_remote_only = remote_ok and not hybrid_ok and not onsite_ok
                if user_remote_only:
                    jd_loc = parsed_jd.location_type.value if parsed_jd.location_type else "Unknown"
                    if jd_loc not in ("Remote", "Unknown"):
                        return False, "You require remote work but this job is not remote."

        # ── Salary floor ──────────────────────────────────────────────────────
        if user_preferences.salary_min_usd and parsed_jd.salary_range:
            job_max = parsed_jd.salary_range.max
            if job_max is not None:
                if job_max < MIN_CREDIBLE_SALARY:
                    logger.warning(
                        f"Ignoring suspicious salary max ${job_max:.0f} "
                        f"(below credibility threshold ${MIN_CREDIBLE_SALARY:,}) — "
                        "treating as unknown."
                    )
                elif job_max < user_preferences.salary_min_usd:
                    return (
                        False,
                        f"Job max salary ${job_max:,.0f} is below your minimum ${user_preferences.salary_min_usd:,.0f}.",
                    )

        return True, None
