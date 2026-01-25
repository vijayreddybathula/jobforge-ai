"""Resume tailoring service."""

from typing import List, Dict, Any, Optional
from uuid import UUID
from packages.schemas.jd_schema import ParsedJD
from packages.schemas.bullet_library import BulletLibrary, Bullet
from packages.common.logging import get_logger

logger = get_logger(__name__)


class ResumeTailor:
    """Tailor resume for specific job."""

    def __init__(self, bullet_library: Optional[BulletLibrary] = None):
        """Initialize resume tailor."""
        self.bullet_library = bullet_library or BulletLibrary()

    def tailor_resume(
        self,
        base_resume_path: str,
        parsed_jd: ParsedJD,
        user_skills: Dict[str, Any],
        output_path: str,
    ) -> Dict[str, Any]:
        """Tailor resume for job.

        Args:
            base_resume_path: Path to base resume
            parsed_jd: Parsed job description
            user_skills: User skills
            output_path: Output path for tailored resume

        Returns:
            Metadata about tailored resume
        """
        # Select relevant bullets
        selected_bullets = self._select_bullets(parsed_jd, user_skills)

        # Reorder and emphasize
        tailored_content = self._reorder_content(selected_bullets, parsed_jd)

        # Generate PDF (simplified - in production use proper PDF library)
        # For now, just return metadata
        metadata = {
            "bullet_ids": [b.id for b in selected_bullets],
            "keyword_coverage": self._calculate_keyword_coverage(selected_bullets, parsed_jd),
            "output_path": output_path,
        }

        logger.info(f"Resume tailored: {len(selected_bullets)} bullets selected")

        return metadata

    def _select_bullets(self, parsed_jd: ParsedJD, user_skills: Dict[str, Any]) -> List[Bullet]:
        """Select relevant bullets from library."""
        # Extract keywords from JD
        keywords = []
        keywords.extend(parsed_jd.must_have_skills)
        keywords.extend(parsed_jd.nice_to_have_skills)
        keywords.extend(parsed_jd.ats_keywords)

        # Get bullets matching keywords
        selected = self.bullet_library.get_bullets_by_tags(keywords)

        # Limit to top matches
        return selected[:10]

    def _reorder_content(self, bullets: List[Bullet], parsed_jd: ParsedJD) -> str:
        """Reorder and format content."""
        # Simple implementation - in production, use proper formatting
        content = "\n".join([bullet.text for bullet in bullets])
        return content

    def _calculate_keyword_coverage(self, bullets: List[Bullet], parsed_jd: ParsedJD) -> float:
        """Calculate keyword coverage percentage."""
        all_keywords = set()
        all_keywords.update(parsed_jd.must_have_skills)
        all_keywords.update(parsed_jd.ats_keywords)

        if not all_keywords:
            return 1.0

        covered = set()
        for bullet in bullets:
            for keyword in all_keywords:
                if keyword.lower() in bullet.text.lower():
                    covered.add(keyword)

        return len(covered) / len(all_keywords) if all_keywords else 0.0
