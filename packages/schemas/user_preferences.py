"""User preferences Pydantic schemas."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class LocationPreferences(BaseModel):
    """Location preferences model."""
    remote_only: bool = False
    hybrid_ok: bool = True
    onsite_ok: bool = False
    preferred_cities: List[str] = []


class UserPreferencesCreate(BaseModel):
    """Schema for creating user preferences."""
    visa_status: Optional[str] = None
    location_preferences: Optional[LocationPreferences] = None
    disability_status: Optional[str] = None
    disability_accommodations: Optional[str] = None
    salary_min_usd: Optional[int] = Field(None, ge=0)
    salary_max_usd: Optional[int] = Field(None, ge=0)
    company_size_preferences: Optional[List[str]] = []  # startup, small, medium, large, enterprise
    industry_preferences: Optional[List[str]] = []
    work_authorization: Optional[str] = None
    other_constraints: Optional[Dict[str, Any]] = {}


class UserPreferencesUpdate(BaseModel):
    """Schema for updating user preferences."""
    visa_status: Optional[str] = None
    location_preferences: Optional[LocationPreferences] = None
    disability_status: Optional[str] = None
    disability_accommodations: Optional[str] = None
    salary_min_usd: Optional[int] = Field(None, ge=0)
    salary_max_usd: Optional[int] = Field(None, ge=0)
    company_size_preferences: Optional[List[str]] = None
    industry_preferences: Optional[List[str]] = None
    work_authorization: Optional[str] = None
    other_constraints: Optional[Dict[str, Any]] = None
    is_ready: Optional[bool] = None


class UserPreferencesResponse(BaseModel):
    """Response schema for user preferences."""
    preferences_id: UUID
    user_id: UUID
    visa_status: Optional[str] = None
    location_preferences: Optional[Dict[str, Any]] = None
    disability_status: Optional[str] = None
    disability_accommodations: Optional[str] = None
    salary_min_usd: Optional[int] = None
    salary_max_usd: Optional[int] = None
    company_size_preferences: Optional[List[str]] = None
    industry_preferences: Optional[List[str]] = None
    work_authorization: Optional[str] = None
    other_constraints: Optional[Dict[str, Any]] = None
    is_ready: bool = False
    created_at: str
    updated_at: str
