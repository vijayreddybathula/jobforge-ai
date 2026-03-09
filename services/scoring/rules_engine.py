"""Rules engine for hard constraint checking."""

from packages.database.models import UserPreferences
from packages.schemas.jd_schema import ParsedJD
from packages.common.logging import get_logger

logger = get_logger(__name__)

# Salary values below this are almost certainly bad parses (hourly rates,
# per-diem figures, $k values that weren't normalised, etc.).
# We treat them as "unknown" and skip the salary constraint rather than
# hard-rejecting what could be a perfectly good job.
MIN_CREDIBLE_SALARY = 10_000  # $10k / year


class RulesEngine:
    """Engine for checking hard constraints before scoring."""

    def check_constraints(self, parsed_jd: ParsedJD, user_preferences: UserPreferences):
        """
        Returns (is_allowed: bool, rejection_reason: str | None).
        Only rejects when we are CONFIDENT the job fails a hard constraint.
        Ambiguous / low-quality parsed values are treated as 'unknown' and
        allowed through so the scoring dimensions can handle them.
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

        # ── Location (remote-only) ────────────────────────────────────────────
        if user_preferences.location_preferences:
            loc = user_preferences.location_preferences
            if isinstance(loc, dict) and loc.get("remote_only", False):
                if parsed_jd.location_type.value not in ("Remote", "Unknown"):
                    return False, "You require remote but this job is not remote."

        # ── Salary floor ──────────────────────────────────────────────────────
        # Only apply if:
        #   1. User has set a minimum salary
        #   2. The job has a parseable max salary
        #   3. That max salary is >= MIN_CREDIBLE_SALARY (not a bad parse)
        if user_preferences.salary_min_usd and parsed_jd.salary_range:
            job_max = parsed_jd.salary_range.max
            if job_max is not None:
                if job_max < MIN_CREDIBLE_SALARY:
                    # Looks like a parsing artifact (e.g. $100 instead of $100k).
                    # Log a warning but DO NOT reject the job.
                    logger.warning(
                        f"Ignoring suspicious salary max ${job_max:.0f} "
                        f"(below credibility threshold ${MIN_CREDIBLE_SALARY:,}) — "
                        "treating as unknown and allowing through."
                    )
                elif job_max < user_preferences.salary_min_usd:
                    return (
                        False,
                        f"Job max salary ${job_max:,.0f} is below your minimum ${user_preferences.salary_min_usd:,.0f}.",
                    )

        return True, None
