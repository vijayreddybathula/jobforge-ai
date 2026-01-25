"""Resume-related Pydantic schemas."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class ResumeUploadRequest(BaseModel):
    """Request schema for resume upload."""

    pass  # File will be in multipart form data


class ResumeUploadResponse(BaseModel):
    """Response schema for resume upload."""

    resume_id: UUID
    file_name: str
    file_type: str
    message: str


class RoleMatch(BaseModel):
    """Role match schema."""

    role_title: str
    confidence_score: int = Field(ge=0, le=100)
    reasoning: Optional[str] = None


class ResumeAnalysisResponse(BaseModel):
    """Response schema for resume analysis."""

    resume_id: UUID
    current_role: Optional[str] = None
    years_of_experience: Optional[int] = None
    core_skills: List[str] = []
    technologies: List[str] = []
    industry_domain: Optional[str] = None
    seniority_level: Optional[str] = None
    suggested_roles: List[RoleMatch] = []
    parsed_sections: Dict[str, Any] = {}


class RoleConfirmationRequest(BaseModel):
    """Request schema for role confirmation."""

    role_title: str
    is_confirmed: bool = True


class RoleConfirmationResponse(BaseModel):
    """Response schema for role confirmation."""

    role_match_id: UUID
    role_title: str
    is_confirmed: bool
    message: str
