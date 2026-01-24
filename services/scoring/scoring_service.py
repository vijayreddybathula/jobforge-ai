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
        self.weights = {
            "core_skill_match": 30,
            "nice_to_have_skills": 20,
            "seniority_alignment": 15,
            "domain_industry": 15,
            "location_fit": 10,
            "compensation": 10
        }
    
    def score_job(
        self,
        job_id: UUID,
        user_id: UUID,
        parsed_jd: ParsedJD,
        user_profile: UserProfile,
        user_preferences: UserPreferences,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Score job fit for user.
        
        Args:
            job_id: Job ID
            user_id: User ID
            parsed_jd: Parsed job description
            user_profile: User profile
            user_preferences: User preferences
            db: Database session
        
        Returns:
            Scoring result dictionary
        """
        if db is None:
            db = next(get_db())
        
        # Check cache first
        cache_key = f"{job_id}:{user_id}"
        cached = self.cache.get_score(str(job_id), str(user_id))
        if cached:
            logger.info(f"Score cache hit for job {job_id}")
            return cached
        
        # Calculate scores
        breakdown = {}
        
        # Core skill match (30 points)
        breakdown["core_skill_match"] = self._score_core_skills(
            parsed_jd.must_have_skills,
            user_profile.skills
        )
        
        # Nice-to-have skills (20 points)
        breakdown["nice_to_have_skills"] = self._score_nice_to_have_skills(
            parsed_jd.nice_to_have_skills,
            user_profile.skills
        )
        
        # Seniority alignment (15 points)
        breakdown["seniority_alignment"] = self._score_seniority(
            parsed_jd.seniority.value,
            user_profile.skills  # Will need to extract seniority from profile
        )
        
        # Domain/industry (15 points)
        breakdown["domain_industry"] = self._score_domain(
            parsed_jd,
            user_profile
        )
        
        # Location fit (10 points)
        breakdown["location_fit"] = self._score_location(
            parsed_jd.location_type.value,
            user_preferences
        )
        
        # Compensation (10 points)
        breakdown["compensation"] = self._score_compensation(
            parsed_jd.salary_range,
            user_preferences
        )
        
        # Calculate total score
        total_score = sum(
            breakdown[key] * (self.weights[key] / 100)
            for key in breakdown.keys()
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
            "rationale": rationale
        }
        
        # Cache result
        self.cache.set_score(str(job_id), str(user_id), result)
        
        # Save to database
        job_score = JobScore(
            job_id=job_id,
            user_id=user_id,
            total_score=total_score,
            breakdown=breakdown,
            verdict=verdict,
            rationale=rationale,
            scoring_version="score-v1"
        )
        
        db.add(job_score)
        db.commit()
        
        logger.info(f"Job scored: {job_id} -> {total_score}/100 ({verdict})")
        
        return result
    
    def _score_core_skills(self, required_skills: list, user_skills: Dict[str, Any]) -> int:
        """Score core skill match (0-100)."""
        if not required_skills:
            return 100  # No requirements = perfect match
        
        user_skills_list = []
        if user_skills:
            user_skills_list.extend(user_skills.get("languages", []))
            user_skills_list.extend(user_skills.get("frameworks", []))
            user_skills_list.extend(user_skills.get("genai", []))
            user_skills_list.extend(user_skills.get("infra", []))
            user_skills_list.extend(user_skills.get("data", []))
        
        user_skills_lower = [s.lower() for s in user_skills_list]
        required_lower = [s.lower() for s in required_skills]
        
        matches = sum(1 for skill in required_lower if any(us in skill or skill in us for us in user_skills_lower))
        
        return int((matches / len(required_skills)) * 100) if required_skills else 0
    
    def _score_nice_to_have_skills(self, nice_skills: list, user_skills: Dict[str, Any]) -> int:
        """Score nice-to-have skills (0-100)."""
        if not nice_skills:
            return 50  # No nice-to-haves = neutral
        
        return self._score_core_skills(nice_skills, user_skills)
    
    def _score_seniority(self, jd_seniority: str, user_skills: Dict[str, Any]) -> int:
        """Score seniority alignment (0-100)."""
        # This is simplified - in production, extract from user profile
        # For now, assume good alignment
        return 80
    
    def _score_domain(self, parsed_jd: ParsedJD, user_profile: UserProfile) -> int:
        """Score domain/industry match (0-100)."""
        # Simplified - in production, compare industries
        return 70
    
    def _score_location(self, location_type: str, user_preferences: UserPreferences) -> int:
        """Score location fit (0-100)."""
        if not user_preferences.location_preferences:
            return 50
        
        loc_prefs = user_preferences.location_preferences
        if isinstance(loc_prefs, dict):
            remote_only = loc_prefs.get("remote_only", False)
            if remote_only:
                return 100 if location_type == "Remote" else 0
            hybrid_ok = loc_prefs.get("hybrid_ok", True)
            if location_type == "Hybrid" and hybrid_ok:
                return 100
            if location_type == "Remote":
                return 100
        
        return 80  # Default good fit
    
    def _score_compensation(self, salary_range: Optional[Any], user_preferences: UserPreferences) -> int:
        """Score compensation fit (0-100)."""
        if not salary_range or not user_preferences.salary_min_usd:
            return 50  # Unknown = neutral
        
        if salary_range.min and salary_range.min >= user_preferences.salary_min_usd:
            return 100
        elif salary_range.max and salary_range.max >= user_preferences.salary_min_usd:
            return 75
        else:
            return 25
    
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
    
    def _generate_rationale(self, score: int, breakdown: Dict[str, int], parsed_jd: ParsedJD) -> str:
        """Generate human-readable rationale."""
        parts = []
        parts.append(f"Overall fit score: {score}/100")
        
        if breakdown.get("core_skill_match", 0) >= 80:
            parts.append("Strong match on required skills")
        elif breakdown.get("core_skill_match", 0) < 50:
            parts.append("Weak match on required skills")
        
        if breakdown.get("location_fit", 0) == 100:
            parts.append("Perfect location match")
        
        if breakdown.get("compensation", 0) >= 75:
            parts.append("Compensation meets expectations")
        
        return ". ".join(parts) + "."
