"""User preferences API — user_id from auth."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID

from packages.database.connection import get_db
from packages.database.models import UserPreferences
from apps.web.auth import get_current_user
from packages.common.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferencesBody(BaseModel):
    visa_status: Optional[str] = None
    work_authorization: Optional[str] = None
    location_preferences: Optional[dict] = None   # {remote, hybrid, onsite, cities}
    salary_min_usd: Optional[int] = None
    salary_max_usd: Optional[int] = None
    company_size_preferences: Optional[List[str]] = None
    industry_preferences: Optional[List[str]] = None
    disability_status: Optional[str] = None
    disability_accommodations: Optional[str] = None
    other_constraints: Optional[dict] = None


def _serialize(p: UserPreferences) -> dict:
    return {
        "preferences_id": str(p.preferences_id),
        "user_id": str(p.user_id),
        "visa_status": p.visa_status,
        "work_authorization": p.work_authorization,
        "location_preferences": p.location_preferences,
        "salary_min_usd": p.salary_min_usd,
        "salary_max_usd": p.salary_max_usd,
        "company_size_preferences": p.company_size_preferences,
        "industry_preferences": p.industry_preferences,
        "disability_status": p.disability_status,
        "is_ready": p.is_ready,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


@router.get("/")
async def get_preferences(
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get preferences for the authenticated user only."""
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == current_user_id).first()
    if not prefs:
        raise HTTPException(status_code=404, detail="Preferences not set yet. Call POST /preferences.")
    return _serialize(prefs)


@router.post("/", status_code=201)
async def create_preferences(
    body: PreferencesBody,
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create preferences for the authenticated user. One record per user."""
    existing = db.query(UserPreferences).filter(UserPreferences.user_id == current_user_id).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Preferences already exist. Use PUT /preferences to update.",
        )

    prefs = UserPreferences(
        user_id=current_user_id,
        **body.dict(exclude_none=True),
        is_ready=True,
    )
    db.add(prefs)
    db.commit()
    db.refresh(prefs)
    logger.info(f"Preferences created for user {current_user_id}")
    return _serialize(prefs)


@router.put("/")
async def update_preferences(
    body: PreferencesBody,
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update preferences for the authenticated user."""
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == current_user_id).first()
    if not prefs:
        raise HTTPException(status_code=404, detail="Preferences not found. Call POST first.")

    for field, value in body.dict(exclude_none=True).items():
        setattr(prefs, field, value)
    prefs.is_ready = True
    db.commit()
    db.refresh(prefs)
    logger.info(f"Preferences updated for user {current_user_id}")
    return _serialize(prefs)


@router.delete("/")
async def delete_preferences(
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete preferences for the authenticated user."""
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == current_user_id).first()
    if not prefs:
        raise HTTPException(status_code=404, detail="Preferences not found.")
    db.delete(prefs)
    db.commit()
    return {"message": "Preferences deleted."}
