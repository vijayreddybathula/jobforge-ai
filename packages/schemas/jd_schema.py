"""Job description parsing schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field, validator
from enum import Enum


class SeniorityLevel(str, Enum):
    INTERN    = "Intern"
    JUNIOR    = "Junior"
    MID       = "Mid"
    SENIOR    = "Senior"
    STAFF     = "Staff"
    PRINCIPAL = "Principal"
    UNKNOWN   = "Unknown"


class EmploymentType(str, Enum):
    FULL_TIME = "Full-time"
    CONTRACT  = "Contract"
    PART_TIME = "Part-time"
    UNKNOWN   = "Unknown"


class LocationType(str, Enum):
    REMOTE  = "Remote"
    HYBRID  = "Hybrid"
    ONSITE  = "Onsite"
    UNKNOWN = "Unknown"


class SalaryRange(BaseModel):
    """Salary range in USD annually.

    LLMs sometimes return salaries in thousands (e.g. 100 meaning $100k),
    or hourly rates (e.g. 50 meaning $50/hr).  We normalise:
      - Values 1–999  → multiply by 1000  (treat as $k shorthand: 150 → $150,000)
      - Values 1000–999  → keep as-is (already annual-ish but suspiciously low; keep)
      - Values < 1 or 0  → treat as unknown / None
    Hourly rates submitted as e.g. 50.0 will become 50,000 which is below any
    reasonable $100k floor, so they'll still get scored (not hard-rejected), —
    the salary scoring dimension will just score low instead.
    """

    min:      Optional[float] = None
    max:      Optional[float] = None
    currency: Optional[str]   = "USD"

    @validator("min", "max", pre=True, always=True)
    def normalise_salary(cls, v):
        if v is None:
            return None
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        if v <= 0:
            return None
        # Values under 1000 are almost certainly expressed in $k (e.g. 150 = $150k)
        if v < 1_000:
            v = v * 1_000
        return v


class ParsedJD(BaseModel):
    """Parsed job description schema."""

    role:               str
    seniority:          SeniorityLevel  = SeniorityLevel.UNKNOWN
    employment_type:    EmploymentType  = EmploymentType.UNKNOWN
    location_type:      LocationType    = LocationType.UNKNOWN
    must_have_skills:   List[str]       = []
    nice_to_have_skills: List[str]      = []
    responsibilities:   List[str]       = []
    ats_keywords:       List[str]       = []
    red_flags:          List[str]       = []
    salary_range:       Optional[SalaryRange] = None

    @validator(
        "must_have_skills",
        "nice_to_have_skills",
        "responsibilities",
        "ats_keywords",
        "red_flags",
        pre=True,
    )
    def ensure_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return list(v) if not isinstance(v, list) else v
