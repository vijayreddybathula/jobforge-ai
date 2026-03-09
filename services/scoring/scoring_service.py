"""Fit scoring service."""

from typing import Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from packages.database.models import JobParsed, UserProfile, UserPreferences, JobScore
from packages.database.connection import get_db
from packages.schemas.jd_schema import ParsedJD
from packages.common.llm_cache import ScoringCache
from packages.common.logging import get_logger
import json
import os

logger = get_logger(__name__)


class ScoringService:
    """Service for scoring job fit."""

    def __init__(self):
        """Initialize scoring service."""
        self.cache = ScoringCache()
        # Weights must sum to 100
        self.weights = {
            "core_skill_match": 30,
            "nice_to_have_skills": 20,
            "seniority_alignment": 15,
            "domain_industry": 15,
            "location_fit": 10,
            "compensation": 10,
        }

    def score_job(
        self,
        job_id: UUID,
        user_id: UUID,
        parsed_jd: ParsedJD,
        user_profile: UserProfile,
        user_preferences: UserPreferences,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Score job fit for user."""
        if db is None:
            db = next(get_db())

        # Check cache first
        cached = self.cache.get_score(str(job_id), str(user_id))
        if cached:
            logger.info(f"Score cache hit for job {job_id}")
            return cached

        # Calculate scores
        breakdown = {}

        # Core skill match (30 points)
        breakdown["core_skill_match"] = self._score_core_skills(
            parsed_jd.must_have_skills, user_profile.skills
        )

        # Nice-to-have skills (20 points)
        breakdown["nice_to_have_skills"] = self._score_nice_to_have_skills(
            parsed_jd.nice_to_have_skills, user_profile.skills
        )

        # Seniority alignment (15 points)
        breakdown["seniority_alignment"] = self._score_seniority(
            parsed_jd.seniority.value if parsed_jd.seniority else "Unknown",
            user_profile.skills,
        )

        # Domain/industry (15 points)
        breakdown["domain_industry"] = self._score_domain(parsed_jd, user_profile)

        # Location fit (10 points)
        breakdown["location_fit"] = self._score_location(
            parsed_jd.location_type.value if parsed_jd.location_type else "Unknown",
            user_preferences,
        )

        # Compensation (10 points)
        breakdown["compensation"] = self._score_compensation(
            parsed_jd.salary_range, user_preferences
        )

        # Calculate total score
        total_score = sum(
            breakdown[key] * (self.weights[key] / 100)
            for key in breakdown
        )
        total_score = int(round(total_score))

        # Generate verdict
        verdict = self._determine_verdict(total_score)

        # Generate rationale
        rationale = self._generate_rationale(total_score, breakdown, parsed_jd)

        result = {
            "job_id": job_id,
            "user_id": user_id,
            "total_score": total_score,
            "breakdown": breakdown,
            "verdict": verdict,
            "rationale": rationale,
        }

        # Cache result
        self.cache.set_score(str(job_id), str(user_id), result)

        # Save to database (upsert: delete old score first so re-scoring works)
        existing = db.query(JobScore).filter(
            JobScore.job_id == job_id, JobScore.user_id == user_id
        ).first()
        if existing:
            db.delete(existing)
            db.commit()

        job_score = JobScore(
            job_id=job_id,
            user_id=user_id,
            total_score=total_score,
            breakdown=breakdown,
            verdict=verdict,
            rationale=rationale,
            scoring_version="score-v1",
        )
        db.add(job_score)
        db.commit()

        logger.info(f"Job scored: {job_id} -> {total_score}/100 ({verdict})")
        return result

    # ── Skill helpers ────────────────────────────────────────────────────────

    def _extract_user_skills_list(self, user_skills: Optional[Dict[str, Any]]) -> list:
        """Flatten all skill buckets from UserProfile.skills into a single list."""
        if not user_skills:
            return []
        all_skills = []
        for bucket in ("languages", "frameworks", "genai", "infra", "data", "tools", "cloud"):
            all_skills.extend(user_skills.get(bucket) or [])
        return all_skills

    def _skills_match_score(self, required: list, user_skills_list: list) -> int:
        """Return 0-100 match percentage using case-insensitive substring matching."""
        if not required:
            return 100  # No requirements → perfect match
        if not user_skills_list:
            return 0

        user_lower = [s.lower() for s in user_skills_list]
        matches = sum(
            1
            for skill in required
            if any(u in skill.lower() or skill.lower() in u for u in user_lower)
        )
        return int((matches / len(required)) * 100)

    def _score_core_skills(self, required_skills: list, user_skills: Optional[Dict[str, Any]]) -> int:
        """Score core skill match (0-100)."""
        return self._skills_match_score(
            required_skills or [],
            self._extract_user_skills_list(user_skills),
        )

    def _score_nice_to_have_skills(self, nice_skills: list, user_skills: Optional[Dict[str, Any]]) -> int:
        """Score nice-to-have skills (0-100)."""
        if not nice_skills:
            return 50  # No nice-to-haves = neutral
        return self._skills_match_score(
            nice_skills,
            self._extract_user_skills_list(user_skills),
        )

    # ── Other dimension helpers ──────────────────────────────────────────────

    def _score_seniority(self, jd_seniority: str, user_skills: Optional[Dict[str, Any]]) -> int:
        """Score seniority alignment (0-100)."""
        # Placeholder — assumes senior-level user. Replace with profile data when available.
        return 80

    def _score_domain(self, parsed_jd: ParsedJD, user_profile: UserProfile) -> int:
        """Score domain/industry match (0-100)."""
        # Placeholder — in production, compare JD domain against user's industry history.
        return 70

    def _score_location(self, location_type: str, user_preferences: UserPreferences) -> int:
        """Score location fit (0-100)."""
        if not user_preferences or not user_preferences.location_preferences:
            return 80  # No explicit preference → assume flexible

        loc_prefs = user_preferences.location_preferences
        if not isinstance(loc_prefs, dict):
            return 80

        remote_only = loc_prefs.get("remote_only", False)
        hybrid_ok   = loc_prefs.get("hybrid_ok", True)

        if location_type == "Remote":
            return 100
        if location_type == "Hybrid":
            return 100 if hybrid_ok else (0 if remote_only else 60)
        if location_type == "Onsite":
            return 0 if remote_only else 60

        # Unknown location type — give partial credit, not 0
        return 60

    def _score_compensation(
        self, salary_range: Optional[Any], user_preferences: UserPreferences
    ) -> int:
        """Score compensation fit (0-100).

        Returns 50 (neutral) whenever salary data is missing on either side.
        Returns 25 only when the JD salary is explicitly below the user's minimum.
        """
        # No user minimum configured → can't evaluate, neutral
        if not user_preferences or not user_preferences.salary_min_usd:
            return 50

        # No salary data in JD (object exists but all values are None) → neutral
        if (
            salary_range is None
            or (getattr(salary_range, "min", None) is None
                and getattr(salary_range, "max", None) is None)
        ):
            return 50

        user_min = user_preferences.salary_min_usd

        if salary_range.min is not None and salary_range.min >= user_min:
            return 100
        if salary_range.max is not None and salary_range.max >= user_min:
            return 75

        # JD salary is explicitly defined and below user minimum
        return 25

    # ── Verdict & rationale ──────────────────────────────────────────────────

    def _determine_verdict(self, score: int) -> str:
        """Determine verdict based on score."""
        if score < 50:
            return "SKIP"
        elif score < 70:
            return "VALIDATE"
        elif score < 85:
            return "ASSISTED_APPLY"
        else:
            return "ELIGIBLE_AUTO_SUBMIT"

    def _generate_rationale(
        self, score: int, breakdown: Dict[str, int], parsed_jd: ParsedJD
    ) -> str:
        """Generate human-readable rationale."""
        parts = [f"Overall fit score: {score}/100"]

        core = breakdown.get("core_skill_match", 0)
        if core >= 80:
            parts.append("Strong match on required skills")
        elif core >= 50:
            parts.append(f"Partial skill match ({core}% of must-haves covered)")
        else:
            parts.append(
                f"Low skill match ({core}% of must-haves). "
                "Tip: ensure your profile skills are populated under Resume → Skills."
            )

        loc = breakdown.get("location_fit", 0)
        if loc == 100:
            parts.append("Perfect location match")
        elif loc == 0:
            parts.append("Location mismatch (remote-only preference vs onsite role)")

        comp = breakdown.get("compensation", 0)
        if comp == 50:
            parts.append("Compensation unknown — salary not listed in JD")
        elif comp >= 75:
            parts.append("Compensation meets expectations")
        elif comp == 25:
            parts.append("Compensation below minimum expectation")

        return ". ".join(parts) + "."
