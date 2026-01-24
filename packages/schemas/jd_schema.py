"""Job description parsing schemas."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class SeniorityLevel(str, Enum):
    """Seniority level enum."""
    INTERN = "Intern"
    JUNIOR = "Junior"
    MID = "Mid"
    SENIOR = "Senior"
    STAFF = "Staff"
    PRINCIPAL = "Principal"
    UNKNOWN = "Unknown"


class EmploymentType(str, Enum):
    """Employment type enum."""
    FULL_TIME = "Full-time"
    CONTRACT = "Contract"
    PART_TIME = "Part-time"
    UNKNOWN = "Unknown"


class LocationType(str, Enum):
    """Location type enum."""
    REMOTE = "Remote"
    HYBRID = "Hybrid"
    ONSITE = "Onsite"
    UNKNOWN = "Unknown"


class SalaryRange(BaseModel):
    """Salary range model."""
    min: Optional[float] = None
    max: Optional[float] = None
    currency: Optional[str] = "USD"


class ParsedJD(BaseModel):
    """Parsed job description schema."""
    role: str
    seniority: SeniorityLevel = SeniorityLevel.UNKNOWN
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    location_type: LocationType = LocationType.UNKNOWN
    must_have_skills: List[str] = []
    nice_to_have_skills: List[str] = []
    responsibilities: List[str] = []
    ats_keywords: List[str] = []
    red_flags: List[str] = []
    salary_range: Optional[SalaryRange] = None
    
    @validator("must_have_skills", "nice_to_have_skills", "responsibilities", "ats_keywords", "red_flags", pre=True)
    def ensure_list(cls, v):
        """Ensure value is a list."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return list(v) if not isinstance(v, list) else v
