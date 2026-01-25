"""Fallback rule-based JD parser."""

import re
from typing import Dict, Any, List
from packages.schemas.jd_schema import ParsedJD, SeniorityLevel, EmploymentType, LocationType
from packages.common.logging import get_logger

logger = get_logger(__name__)


class FallbackParser:
    """Rule-based fallback parser for when LLM fails."""

    # Common skill keywords
    SKILL_KEYWORDS = {
        "python": "Python",
        "java": "Java",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "react": "React",
        "node": "Node.js",
        "aws": "AWS",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "sql": "SQL",
        "postgresql": "PostgreSQL",
        "mongodb": "MongoDB",
        "redis": "Redis",
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
    }

    # Seniority keywords
    SENIORITY_KEYWORDS = {
        "intern": SeniorityLevel.INTERN,
        "junior": SeniorityLevel.JUNIOR,
        "mid": SeniorityLevel.MID,
        "senior": SeniorityLevel.SENIOR,
        "staff": SeniorityLevel.STAFF,
        "principal": SeniorityLevel.PRINCIPAL,
    }

    # Employment type keywords
    EMPLOYMENT_KEYWORDS = {
        "full.time": EmploymentType.FULL_TIME,
        "fulltime": EmploymentType.FULL_TIME,
        "contract": EmploymentType.CONTRACT,
        "part.time": EmploymentType.PART_TIME,
        "parttime": EmploymentType.PART_TIME,
    }

    # Location type keywords
    LOCATION_KEYWORDS = {
        "remote": LocationType.REMOTE,
        "hybrid": LocationType.HYBRID,
        "on.site": LocationType.ONSITE,
        "onsite": LocationType.ONSITE,
        "in.person": LocationType.ONSITE,
    }

    def parse(self, jd_text: str) -> ParsedJD:
        """Parse JD using rule-based extraction.

        Args:
            jd_text: Job description text

        Returns:
            Parsed JD object
        """
        jd_lower = jd_text.lower()

        # Extract role (first line or title-like text)
        role = self._extract_role(jd_text)

        # Extract seniority
        seniority = self._extract_seniority(jd_lower)

        # Extract employment type
        employment_type = self._extract_employment_type(jd_lower)

        # Extract location type
        location_type = self._extract_location_type(jd_lower)

        # Extract skills
        must_have_skills = self._extract_skills(jd_lower)
        nice_to_have_skills = []  # Hard to distinguish without LLM

        # Extract responsibilities (bullet points)
        responsibilities = self._extract_responsibilities(jd_text)

        # Extract ATS keywords (common tech terms)
        ats_keywords = self._extract_ats_keywords(jd_lower)

        # Extract red flags
        red_flags = self._extract_red_flags(jd_lower)

        # Extract salary range
        salary_range = self._extract_salary_range(jd_text)

        return ParsedJD(
            role=role,
            seniority=seniority,
            employment_type=employment_type,
            location_type=location_type,
            must_have_skills=must_have_skills,
            nice_to_have_skills=nice_to_have_skills,
            responsibilities=responsibilities,
            ats_keywords=ats_keywords,
            red_flags=red_flags,
            salary_range=salary_range,
        )

    def _extract_role(self, jd_text: str) -> str:
        """Extract job role/title."""
        # Try to find title in first few lines
        lines = jd_text.split("\n")[:5]
        for line in lines:
            line = line.strip()
            if line and len(line) < 100:  # Title-like
                return line
        return "Unknown"

    def _extract_seniority(self, jd_lower: str) -> SeniorityLevel:
        """Extract seniority level."""
        for keyword, level in self.SENIORITY_KEYWORDS.items():
            if re.search(rf"\b{keyword}\b", jd_lower):
                return level
        return SeniorityLevel.UNKNOWN

    def _extract_employment_type(self, jd_lower: str) -> EmploymentType:
        """Extract employment type."""
        for keyword, emp_type in self.EMPLOYMENT_KEYWORDS.items():
            if re.search(rf"\b{keyword}\b", jd_lower):
                return emp_type
        return EmploymentType.UNKNOWN

    def _extract_location_type(self, jd_lower: str) -> LocationType:
        """Extract location type."""
        for keyword, loc_type in self.LOCATION_KEYWORDS.items():
            if re.search(rf"\b{keyword}\b", jd_lower):
                return loc_type
        return LocationType.UNKNOWN

    def _extract_skills(self, jd_lower: str) -> List[str]:
        """Extract skills."""
        skills = []
        for keyword, skill_name in self.SKILL_KEYWORDS.items():
            if re.search(rf"\b{keyword}\b", jd_lower):
                skills.append(skill_name)
        return list(set(skills))  # Remove duplicates

    def _extract_responsibilities(self, jd_text: str) -> List[str]:
        """Extract responsibilities (bullet points)."""
        responsibilities = []
        # Look for bullet points
        bullet_pattern = r"[•\-\*]\s*(.+?)(?=\n[•\-\*]|\n\n|$)"
        matches = re.findall(bullet_pattern, jd_text, re.MULTILINE)
        responsibilities.extend([m.strip() for m in matches[:10]])  # Limit to 10
        return responsibilities

    def _extract_ats_keywords(self, jd_lower: str) -> List[str]:
        """Extract ATS keywords."""
        return self._extract_skills(jd_lower)  # Similar to skills

    def _extract_red_flags(self, jd_lower: str) -> List[str]:
        """Extract red flags."""
        red_flags = []
        red_flag_patterns = [
            r"requires\s+(us\s+)?citizenship",
            r"security\s+clearance",
            r"must\s+be\s+onsite",
            r"no\s+remote",
        ]
        for pattern in red_flag_patterns:
            if re.search(pattern, jd_lower):
                red_flags.append(pattern.replace(r"\s+", " "))
        return red_flags

    def _extract_salary_range(self, jd_text: str):
        """Extract salary range."""
        # Look for salary patterns like $100k-$150k or $100,000 - $150,000
        salary_pattern = r"\$(\d+(?:,\d{3})*(?:k)?)\s*[-–]\s*\$(\d+(?:,\d{3})*(?:k)?)"
        match = re.search(salary_pattern, jd_text, re.IGNORECASE)

        if match:
            min_str = match.group(1).replace(",", "").replace("k", "000")
            max_str = match.group(2).replace(",", "").replace("k", "000")
            try:
                from packages.schemas.jd_schema import SalaryRange

                return SalaryRange(min=float(min_str), max=float(max_str), currency="USD")
            except ValueError:
                pass

        return None
