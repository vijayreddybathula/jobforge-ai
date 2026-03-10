"""Fit scoring service."""

from typing import Any, Dict, List, Optional
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
    """Lower-case, strip parenthetical aliases and punctuation."""
    s = s.lower()
    s = re.sub(r'[()\[\]]', ' ', s)
    s = re.sub(r'[-/]', ' ', s)
    return ' '.join(s.split())


def _skill_match(jd_skill: str, user_skills_normalised: List[str]) -> bool:
    """Return True if jd_skill fuzzy-matches any skill in the user list."""
    norm_jd = _normalise_skill(jd_skill)
    jd_tokens = set(norm_jd.split())
    for us in user_skills_normalised:
        if norm_jd in us or us in norm_jd:
            return True
        us_tokens = set(us.split())
        shared = jd_tokens & us_tokens
        meaningful = shared - {'and', 'or', 'the', 'of', 'with', 'for', 'in', 'a'}
        if meaningful:
            return True
    return False


def _flatten_user_skills(user_skills: Optional[Dict[str, Any]]) -> List[str]:
    """Flatten every value in the skills dict into a single list."""
    if not user_skills:
        return []
    skills: List[str] = []
    for v in user_skills.values():
        if isinstance(v, list):
            skills.extend(str(x) for x in v if x)
        elif isinstance(v, str) and v:
            skills.append(v)
    return skills


def _user_seniority_from_roles(core_roles: Optional[List[str]]) -> str:
    """
    Infer the user's own seniority level from their confirmed role titles.
    Returns a normalised string: 'principal', 'senior', 'mid', 'junior', or 'unknown'.

    Examples:
      ['Senior GenAI Engineer']        -> 'senior'
      ['Principal ML Engineer']        -> 'principal'
      ['Software Engineer II']         -> 'mid'
      ['Junior Data Analyst']          -> 'junior'
      ['Data Scientist']               -> 'unknown'  (no seniority signal)
    """
    if not core_roles:
        return 'unknown'
    combined = ' '.join(core_roles).lower()
    if any(t in combined for t in ('principal', 'staff', 'distinguished', 'fellow')):
        return 'principal'
    if any(t in combined for t in ('senior', 'sr.', 'sr ', 'lead', 'manager', 'head of')):
        return 'senior'
    if any(t in combined for t in ('junior', 'jr', 'entry', 'associate', 'intern')):
        return 'junior'
    if any(t in combined for t in (' ii', ' iii', 'level 2', 'level 3', 'mid')):
        return 'mid'
    return 'unknown'


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

        verdict   = self._determine_verdict(total_score)
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

        existing = db.query(JobScore).filter(
            JobScore.job_id == job_id,
            JobScore.user_id == user_id,
        ).first()
        if existing:
            db.delete(existing)
            db.flush()

        db.add(JobScore(
            job_id=job_id,
            user_id=user_id,
            total_score=total_score,
            breakdown=breakdown,
            verdict=verdict,
            rationale=rationale,
            scoring_version="score-v3",
        ))
        db.commit()

        logger.info(f"Job scored: {job_id} -> {total_score}/100 ({verdict})")
        return result

    # ── Dimension scorers ─────────────────────────────────────────────────────

    def _score_core_skills(
        self, required_skills: Optional[List[str]], user_skills: Optional[Dict[str, Any]]
    ) -> int:
        if not required_skills:
            return 100
        user_list = _flatten_user_skills(user_skills)
        if not user_list:
            return 0
        user_normalised = [_normalise_skill(s) for s in user_list]
        matches = sum(1 for s in required_skills if _skill_match(s, user_normalised))
        return int((matches / len(required_skills)) * 100)

    def _score_nice_to_have_skills(
        self, nice_skills: Optional[List[str]], user_skills: Optional[Dict[str, Any]]
    ) -> int:
        if not nice_skills:
            return 50
        return self._score_core_skills(nice_skills, user_skills)

    def _score_seniority(
        self, jd_seniority: str, user_profile: UserProfile
    ) -> int:
        """
        Score seniority alignment 0-100.

        Compares JD seniority level against the seniority signal embedded
        in the user's own confirmed role titles (core_roles).

        Match matrix:
          user=principal vs jd=principal/staff  → 100  (exact)
          user=principal vs jd=senior            → 85   (slightly overqualified)
          user=senior    vs jd=senior/lead        → 100  (exact)
          user=senior    vs jd=principal          → 75   (stretch)
          user=senior    vs jd=mid                → 80   (overqualified)
          user=senior    vs jd=junior             → 60   (overqualified)
          user=mid       vs jd=mid                → 100
          user=mid       vs jd=senior             → 65   (under)
          user=junior    vs jd=junior             → 100
          user=junior    vs jd=senior             → 40   (under)
          user=unknown   vs any                   → 75   (neutral)
        """
        jd   = (jd_seniority or 'mid').lower()
        user = _user_seniority_from_roles(user_profile.core_roles)

        # Determine JD bucket
        if any(t in jd for t in ('principal', 'staff', 'distinguished')):
            jd_level = 'principal'
        elif any(t in jd for t in ('senior', 'sr.', 'sr ', 'lead')):
            jd_level = 'senior'
        elif any(t in jd for t in ('junior', 'jr', 'entry', 'associate')):
            jd_level = 'junior'
        elif any(t in jd for t in ('mid', ' ii', 'level 2')):
            jd_level = 'mid'
        else:
            jd_level = 'mid'  # Unknown JD level defaults to mid

        if user == 'unknown':
            return 75  # Can't evaluate — neutral

        MATRIX = {
            ('principal', 'principal'): 100,
            ('principal', 'senior'):     85,
            ('principal', 'mid'):        70,
            ('principal', 'junior'):     55,
            ('senior',    'principal'):  75,
            ('senior',    'senior'):    100,
            ('senior',    'mid'):        80,
            ('senior',    'junior'):     60,
            ('mid',       'principal'):  55,
            ('mid',       'senior'):     65,
            ('mid',       'mid'):       100,
            ('mid',       'junior'):     80,
            ('junior',    'principal'):  35,
            ('junior',    'senior'):     40,
            ('junior',    'mid'):        70,
            ('junior',    'junior'):    100,
        }
        return MATRIX.get((user, jd_level), 75)

    def _score_domain(
        self, parsed_jd: ParsedJD, user_profile: UserProfile
    ) -> int:
        """
        Score domain/industry match 0-100.

        Cross-matches JD ATS keywords against all user skills (all buckets)
        using the same fuzzy matching as core skill scoring.
        Fully dynamic — works for any domain/field.
        """
        ats_keywords = parsed_jd.ats_keywords or []
        if not ats_keywords:
            return 60  # JD has no ATS keywords — neutral

        user_skill_list = _flatten_user_skills(user_profile.skills)
        if not user_skill_list:
            logger.info("domain_industry: no user skills found, returning neutral 50")
            return 50  # New user — neutral, not penalised

        user_normalised = [_normalise_skill(s) for s in user_skill_list]
        matched = sum(1 for kw in ats_keywords if _skill_match(kw, user_normalised))
        pct = matched / len(ats_keywords)

        logger.info(
            f"domain_industry: {matched}/{len(ats_keywords)} ATS keywords matched "
            f"({pct:.0%}) — user has {len(user_skill_list)} skills"
        )

        if pct >= 0.50:
            return 90
        elif pct >= 0.25:
            return 70
        elif matched >= 1:
            return 50
        else:
            return 30

    def _score_location(
        self, location_type: str, user_preferences: UserPreferences
    ) -> int:
        """
        Score location fit 0-100.

        Reads location_preferences keys exactly as PreferencesPage saves them:
          { remote: bool, hybrid: bool, onsite: bool, cities: [...] }

        (Previous bug: was reading remote_only / hybrid_ok / onsite_ok which
        never existed in the DB, so all lookups returned the default value.)
        """
        if not user_preferences or not user_preferences.location_preferences:
            return 80

        loc = user_preferences.location_preferences
        if not isinstance(loc, dict):
            return 80

        # Read the correct keys saved by PreferencesPage
        remote_ok = loc.get("remote",  False)
        hybrid_ok = loc.get("hybrid",  False)
        onsite_ok = loc.get("onsite",  False)

        # If nothing is checked at all, treat as flexible
        if not remote_ok and not hybrid_ok and not onsite_ok:
            return 80

        loc_lower = (location_type or "unknown").lower()

        if loc_lower == "remote":
            return 100 if remote_ok else (40 if not hybrid_ok and not onsite_ok else 50)
        if loc_lower == "hybrid":
            return 100 if hybrid_ok else (60 if remote_ok else 30)
        if loc_lower in ("onsite", "in-person", "in person"):
            return 100 if onsite_ok else (30 if not hybrid_ok else 40)
        return 70  # Unknown location type — benefit of the doubt

    def _score_compensation(
        self, salary_range: Optional[Any], user_preferences: UserPreferences
    ) -> int:
        """Score compensation fit 0-100. Returns 50 when JD has no salary data."""
        if not salary_range:
            return 50

        sal_min = getattr(salary_range, 'min', None)
        sal_max = getattr(salary_range, 'max', None)

        if sal_min is None and sal_max is None:
            return 50

        if not user_preferences or not user_preferences.salary_min_usd:
            return 75  # Salary exists but no user threshold — good sign

        user_min = user_preferences.salary_min_usd

        if sal_min and sal_min >= user_min:
            return 100
        elif sal_max and sal_max >= user_min:
            return 75
        elif sal_max and sal_max >= user_min * 0.85:
            return 50
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
        parts = [f"Overall fit score: {score}/100"]

        csm = breakdown.get("core_skill_match", 0)
        if csm >= 80:
            parts.append("Strong match on required skills")
        elif csm >= 50:
            parts.append(f"Partial skill match ({csm}%)")
        else:
            if parsed_jd.must_have_skills and user_profile and user_profile.skills:
                user_normalised = [
                    _normalise_skill(s)
                    for s in _flatten_user_skills(user_profile.skills)
                ]
                missing = [
                    s for s in (parsed_jd.must_have_skills or [])
                    if not _skill_match(s, user_normalised)
                ][:5]
                if missing:
                    parts.append(f"Missing skills: {', '.join(missing)}")
                else:
                    parts.append("Weak skill signal in profile")
            else:
                parts.append(
                    "Weak match on required skills — "
                    "populate Resume → Skills to improve accuracy"
                )

        dom = breakdown.get("domain_industry", 0)
        if dom >= 90:
            parts.append("Strong domain alignment")
        elif dom >= 70:
            parts.append("Reasonable domain overlap")
        elif dom <= 30:
            parts.append("Low domain overlap — job may be outside your current skill set")

        loc = breakdown.get("location_fit", 0)
        if loc == 100:
            parts.append("Perfect location match")
        elif loc <= 30:
            parts.append("Location mismatch with your preferences")

        comp = breakdown.get("compensation", 0)
        if comp == 50:
            parts.append("Compensation not disclosed")
        elif comp >= 75:
            parts.append("Compensation meets expectations")
        elif comp == 25:
            parts.append("Compensation below your minimum target")

        sen = breakdown.get("seniority_alignment", 0)
        if sen >= 100:
            parts.append("Seniority level is a great match")
        elif sen <= 40:
            parts.append("Seniority mismatch — role may be too junior or too senior")

        return ". ".join(parts) + "."
