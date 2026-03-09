"""Fit scoring service."""

from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
import re

from packages.database.models import JobParsed, UserProfile, UserPreferences, JobScore
from packages.database.connection import get_db
from packages.schemas.jd_schema import ParsedJD
from packages.common.llm_cache import ScoringCache
from packages.common.logging import get_logger

logger = get_logger(__name__)


def _normalise_skill(s: str) -> str:
    """Lower-case, strip parenthetical aliases and punctuation for fuzzy comparison.

    Examples:
        'Retrieval-Augmented Generation (RAG)' -> 'retrieval augmented generation rag'
        'LangGraph'                             -> 'langgraph'
        'Pytest'                                -> 'pytest'
    """
    s = s.lower()
    # expand parenthetical aliases: "foo (bar)" -> "foo bar"
    s = re.sub(r'[()\[\]]', ' ', s)
    # replace hyphens/slashes with space
    s = re.sub(r'[-/]', ' ', s)
    # collapse whitespace
    return ' '.join(s.split())


def _skill_match(jd_skill: str, user_skills_normalised: List[str]) -> bool:
    """Return True if jd_skill fuzzy-matches any skill in the user list.

    Strategy:
    1. Direct substring: 'rag' in 'retrieval augmented generation rag' ✓
    2. Token overlap: if the JD skill has ≥2 tokens AND any single token
       appears in a user skill token set — catches 'langchain' inside
       'langchain agents', etc.
    """
    norm_jd = _normalise_skill(jd_skill)
    jd_tokens = set(norm_jd.split())

    for us in user_skills_normalised:
        # substring both ways
        if norm_jd in us or us in norm_jd:
            return True
        # token overlap (at least one meaningful token shared)
        us_tokens = set(us.split())
        shared = jd_tokens & us_tokens
        # ignore trivial stop-tokens
        meaningful = shared - {'and', 'or', 'the', 'of', 'with', 'for', 'in', 'a'}
        if meaningful:
            return True
    return False


def _flatten_user_skills(user_skills: Optional[Dict[str, Any]]) -> List[str]:
    """Flatten every value in the skills dict into a single list.

    Handles any storage shape — whether the profile stores skills under
    'languages'/'frameworks'/'genai'/... or a flat list or any other keys.
    """
    if not user_skills:
        return []
    skills: List[str] = []
    for v in user_skills.values():
        if isinstance(v, list):
            skills.extend(str(x) for x in v if x)
        elif isinstance(v, str) and v:
            skills.append(v)
    return skills


class ScoringService:
    """Service for scoring job fit."""

    def __init__(self):
        self.cache = ScoringCache()
        self.weights = {
            "core_skill_match":    0.30,
            "nice_to_have_skills": 0.20,
            "seniority_alignment": 0.15,
            "domain_industry":     0.15,
            "location_fit":        0.10,
            "compensation":        0.10,
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
        """Score job fit for a user and persist result."""
        if db is None:
            db = next(get_db())

        cached = self.cache.get_score(str(job_id), str(user_id))
        if cached:
            logger.info(f"Score cache hit for job {job_id}")
            return cached

        breakdown: Dict[str, int] = {}

        breakdown["core_skill_match"] = self._score_core_skills(
            parsed_jd.must_have_skills, user_profile.skills
        )
        breakdown["nice_to_have_skills"] = self._score_nice_to_have_skills(
            parsed_jd.nice_to_have_skills, user_profile.skills
        )
        breakdown["seniority_alignment"] = self._score_seniority(
            parsed_jd.seniority.value if parsed_jd.seniority else "Mid",
            user_profile,
        )
        breakdown["domain_industry"] = self._score_domain(parsed_jd, user_profile)
        breakdown["location_fit"] = self._score_location(
            parsed_jd.location_type.value if parsed_jd.location_type else "Unknown",
            user_preferences,
        )
        breakdown["compensation"] = self._score_compensation(
            parsed_jd.salary_range, user_preferences
        )

        total_score = int(round(
            sum(breakdown[k] * self.weights[k] for k in breakdown)
        ))

        verdict  = self._determine_verdict(total_score)
        rationale = self._generate_rationale(total_score, breakdown, parsed_jd, user_profile)

        result = {
            "job_id":      job_id,
            "user_id":     user_id,
            "total_score": total_score,
            "breakdown":   breakdown,
            "verdict":     verdict,
            "rationale":   rationale,
        }

        self.cache.set_score(str(job_id), str(user_id), result)

        job_score = JobScore(
            job_id=job_id,
            user_id=user_id,
            total_score=total_score,
            breakdown=breakdown,
            verdict=verdict,
            rationale=rationale,
            scoring_version="score-v2",
        )
        db.add(job_score)
        db.commit()

        logger.info(f"Job scored: {job_id} -> {total_score}/100 ({verdict})")
        return result

    # ── Dimension scorers ─────────────────────────────────────────────────────

    def _score_core_skills(
        self, required_skills: Optional[List[str]], user_skills: Optional[Dict[str, Any]]
    ) -> int:
        """Score core skill match 0-100.

        Flattens all keys from user_skills so the scorer is robust to any
        profile storage shape, then uses fuzzy token matching.
        """
        if not required_skills:
            return 100  # no requirements = perfect

        user_list = _flatten_user_skills(user_skills)
        if not user_list:
            return 0

        user_normalised = [_normalise_skill(s) for s in user_list]

        matches = sum(
            1 for skill in required_skills
            if _skill_match(skill, user_normalised)
        )
        return int((matches / len(required_skills)) * 100)

    def _score_nice_to_have_skills(
        self, nice_skills: Optional[List[str]], user_skills: Optional[Dict[str, Any]]
    ) -> int:
        """Score nice-to-have skills 0-100."""
        if not nice_skills:
            return 50  # no nice-to-haves = neutral
        return self._score_core_skills(nice_skills, user_skills)

    def _score_seniority(
        self, jd_seniority: str, user_profile: UserProfile
    ) -> int:
        """Score seniority alignment 0-100."""
        # Extract years of experience from profile if available
        years = 0
        if user_profile.experience_years:
            years = user_profile.experience_years

        seniority_lower = jd_seniority.lower()

        if "senior" in seniority_lower or "sr" in seniority_lower or "lead" in seniority_lower:
            if years >= 5:
                return 95
            elif years >= 3:
                return 75
            else:
                return 50
        elif "mid" in seniority_lower or "ii" in seniority_lower:
            if years >= 2:
                return 90
            else:
                return 70
        elif "junior" in seniority_lower or "jr" in seniority_lower or "entry" in seniority_lower:
            return 60  # over-qualified is better than under
        elif "principal" in seniority_lower or "staff" in seniority_lower:
            if years >= 8:
                return 90
            elif years >= 5:
                return 75
            else:
                return 50
        # Unknown seniority — assume reasonable match
        return 80

    def _score_domain(
        self, parsed_jd: ParsedJD, user_profile: UserProfile
    ) -> int:
        """Score domain/industry match 0-100."""
        # Check ATS keywords against user's GenAI/AI domain keywords
        ai_keywords = {
            'genai', 'llm', 'ai', 'ml', 'machine learning', 'deep learning',
            'nlp', 'generative', 'openai', 'langchain', 'rag', 'vector',
            'embedding', 'transformer', 'gpt', 'azure openai', 'agentic',
        }
        jd_ats = {k.lower() for k in (parsed_jd.ats_keywords or [])}
        domain_overlap = jd_ats & ai_keywords
        if len(domain_overlap) >= 3:
            return 90
        elif len(domain_overlap) >= 1:
            return 70
        return 50

    def _score_location(
        self, location_type: str, user_preferences: UserPreferences
    ) -> int:
        """Score location fit 0-100."""
        if not user_preferences or not user_preferences.location_preferences:
            return 80  # no preference = assume it works

        loc_prefs = user_preferences.location_preferences
        if not isinstance(loc_prefs, dict):
            return 80

        remote_only = loc_prefs.get("remote_only", False)
        hybrid_ok   = loc_prefs.get("hybrid_ok", True)
        onsite_ok   = loc_prefs.get("onsite_ok", False)
        loc_lower   = location_type.lower() if location_type else "unknown"

        if loc_lower == "remote":
            return 100
        if loc_lower == "hybrid":
            return 100 if hybrid_ok else (50 if not remote_only else 30)
        if loc_lower in ("onsite", "in-person", "in person"):
            return 80 if onsite_ok else (40 if not remote_only else 10)
        # Unknown location type — give benefit of the doubt
        return 70

    def _score_compensation(
        self, salary_range: Optional[Any], user_preferences: UserPreferences
    ) -> int:
        """Score compensation fit 0-100.

        Returns 50 (neutral) whenever the JD has no salary data — we should
        not penalise a job just because it doesn't publish its range.
        """
        # No salary in JD → neutral, not a penalty
        if not salary_range:
            return 50

        sal_min = getattr(salary_range, 'min', None)
        sal_max = getattr(salary_range, 'max', None)

        if sal_min is None and sal_max is None:
            return 50  # salary unknown → neutral

        if not user_preferences or not user_preferences.salary_min_usd:
            return 75  # we have some salary data but no user threshold → good sign

        user_min = user_preferences.salary_min_usd

        if sal_min and sal_min >= user_min:
            return 100
        elif sal_max and sal_max >= user_min:
            return 75
        elif sal_max and sal_max >= user_min * 0.85:
            return 50  # close but slightly below
        else:
            return 25

    # ── Verdict & rationale ───────────────────────────────────────────────────

    def _determine_verdict(self, score: int) -> str:
        if score >= 85:
            return "ELIGIBLE_AUTO_SUBMIT"
        elif score >= 70:
            return "ASSISTED_APPLY"
        elif score >= 50:
            return "VALIDATE"
        else:
            return "SKIP"

    def _generate_rationale(
        self,
        score: int,
        breakdown: Dict[str, int],
        parsed_jd: ParsedJD,
        user_profile: Optional[UserProfile] = None,
    ) -> str:
        """Generate actionable human-readable rationale."""
        parts = [f"Overall fit score: {score}/100"]

        csm = breakdown.get("core_skill_match", 0)
        if csm >= 80:
            parts.append("Strong match on required skills")
        elif csm >= 50:
            parts.append(f"Partial skill match ({csm}%)")
        else:
            # Surface the missing skills so users know what to highlight
            if parsed_jd.must_have_skills and user_profile and user_profile.skills:
                user_normalised = [_normalise_skill(s) for s in _flatten_user_skills(user_profile.skills)]
                missing = [
                    s for s in (parsed_jd.must_have_skills or [])
                    if not _skill_match(s, user_normalised)
                ][:5]  # cap at 5 to keep rationale readable
                if missing:
                    parts.append(f"Missing skills: {', '.join(missing)}")
                else:
                    parts.append("Weak skill signal in profile")
            else:
                parts.append("Weak match on required skills")

        loc = breakdown.get("location_fit", 0)
        if loc == 100:
            parts.append("Perfect location match")
        elif loc <= 30:
            parts.append("Location mismatch")

        comp = breakdown.get("compensation", 0)
        if comp == 50:
            parts.append("Compensation not disclosed")
        elif comp >= 75:
            parts.append("Compensation meets expectations")
        elif comp == 25:
            parts.append("Compensation below target")

        return ". ".join(parts) + "."
