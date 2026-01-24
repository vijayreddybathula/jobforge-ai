"""Recruiter pitch generator."""

from typing import Dict, Any
from packages.schemas.jd_schema import ParsedJD
from packages.common.logging import get_logger

logger = get_logger(__name__)


class PitchGenerator:
    """Generate recruiter pitch."""
    
    def generate(
        self,
        parsed_jd: ParsedJD,
        user_skills: Dict[str, Any],
        score: int
    ) -> str:
        """Generate recruiter pitch.
        
        Args:
            parsed_jd: Parsed job description
            user_skills: User skills
            score: Fit score
        
        Returns:
            Recruiter pitch text
        """
        # Extract top skills match
        matched_skills = []
        user_skills_list = []
        if user_skills:
            user_skills_list.extend(user_skills.get("languages", []))
            user_skills_list.extend(user_skills.get("frameworks", []))
        
        for skill in parsed_jd.must_have_skills[:5]:
            if any(us.lower() in skill.lower() or skill.lower() in us.lower() for us in user_skills_list):
                matched_skills.append(skill)
        
        # Generate pitch
        pitch_parts = []
        
        pitch_parts.append(f"I'm excited to apply for the {parsed_jd.role} position.")
        
        if matched_skills:
            pitch_parts.append(f"I have strong experience with {', '.join(matched_skills[:3])}, which align perfectly with your requirements.")
        
        if score >= 80:
            pitch_parts.append("I believe my background makes me an excellent fit for this role.")
        else:
            pitch_parts.append("I'm confident I can contribute to your team.")
        
        pitch = " ".join(pitch_parts)
        
        logger.info(f"Pitch generated for {parsed_jd.role}")
        
        return pitch
