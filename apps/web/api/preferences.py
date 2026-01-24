"""User preferences API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from packages.database.connection import get_db
from packages.database.models import UserPreferences, User
from packages.schemas.user_preferences import (
    UserPreferencesCreate,
    UserPreferencesUpdate,
    UserPreferencesResponse
)
from packages.common.redis_cache import get_redis_cache
from packages.common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/preferences", tags=["preferences"])


def _get_cache_key(user_id: UUID) -> str:
    """Get Redis cache key for user preferences."""
    return f"user:prefs:{user_id}"


@router.get("", response_model=UserPreferencesResponse)
async def get_preferences(
    db: Session = Depends(get_db),
    # user_id: UUID = Depends(get_current_user)  # TODO: Add authentication
):
    """Get user preferences (with Redis cache)."""
    # TODO: Get user_id from authenticated user
    user_id = UUID("00000000-0000-0000-0000-000000000001")  # Placeholder
    
    cache = get_redis_cache()
    cache_key = _get_cache_key(user_id)
    
    # Try cache first
    cached = cache.get(cache_key)
    if cached:
        logger.debug(f"Preferences cache hit for user {user_id}")
        return UserPreferencesResponse(**cached)
    
    # Get from database
    preferences = db.query(UserPreferences).filter(
        UserPreferences.user_id == user_id
    ).first()
    
    if not preferences:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preferences not found. Please create preferences first."
        )
    
    # Convert to response
    response_data = {
        "preferences_id": preferences.preferences_id,
        "user_id": preferences.user_id,
        "visa_status": preferences.visa_status,
        "location_preferences": preferences.location_preferences,
        "disability_status": preferences.disability_status,
        "disability_accommodations": preferences.disability_accommodations,
        "salary_min_usd": preferences.salary_min_usd,
        "salary_max_usd": preferences.salary_max_usd,
        "company_size_preferences": preferences.company_size_preferences,
        "industry_preferences": preferences.industry_preferences,
        "work_authorization": preferences.work_authorization,
        "other_constraints": preferences.other_constraints,
        "is_ready": preferences.is_ready,
        "created_at": preferences.created_at.isoformat(),
        "updated_at": preferences.updated_at.isoformat()
    }
    
    # Cache response (1 hour TTL)
    cache.set(cache_key, response_data, ttl=3600)
    
    return UserPreferencesResponse(**response_data)


@router.post("", response_model=UserPreferencesResponse)
async def create_preferences(
    preferences: UserPreferencesCreate,
    db: Session = Depends(get_db),
    # user_id: UUID = Depends(get_current_user)  # TODO: Add authentication
):
    """Create user preferences."""
    # TODO: Get user_id from authenticated user
    user_id = UUID("00000000-0000-0000-0000-000000000001")  # Placeholder
    
    # Check if user exists
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if preferences already exist
    existing = db.query(UserPreferences).filter(
        UserPreferences.user_id == user_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Preferences already exist. Use PUT to update."
        )
    
    # Create preferences
    db_preferences = UserPreferences(
        user_id=user_id,
        visa_status=preferences.visa_status,
        location_preferences=preferences.location_preferences.dict() if preferences.location_preferences else None,
        disability_status=preferences.disability_status,
        disability_accommodations=preferences.disability_accommodations,
        salary_min_usd=preferences.salary_min_usd,
        salary_max_usd=preferences.salary_max_usd,
        company_size_preferences=preferences.company_size_preferences,
        industry_preferences=preferences.industry_preferences,
        work_authorization=preferences.work_authorization,
        other_constraints=preferences.other_constraints,
        is_ready=False
    )
    
    db.add(db_preferences)
    db.commit()
    db.refresh(db_preferences)
    
    # Invalidate cache
    cache = get_redis_cache()
    cache.delete(_get_cache_key(user_id))
    
    logger.info(f"Preferences created for user {user_id}")
    
    return UserPreferencesResponse(
        preferences_id=db_preferences.preferences_id,
        user_id=db_preferences.user_id,
        visa_status=db_preferences.visa_status,
        location_preferences=db_preferences.location_preferences,
        disability_status=db_preferences.disability_status,
        disability_accommodations=db_preferences.disability_accommodations,
        salary_min_usd=db_preferences.salary_min_usd,
        salary_max_usd=db_preferences.salary_max_usd,
        company_size_preferences=db_preferences.company_size_preferences,
        industry_preferences=db_preferences.industry_preferences,
        work_authorization=db_preferences.work_authorization,
        other_constraints=db_preferences.other_constraints,
        is_ready=db_preferences.is_ready,
        created_at=db_preferences.created_at.isoformat(),
        updated_at=db_preferences.updated_at.isoformat()
    )


@router.put("", response_model=UserPreferencesResponse)
async def update_preferences(
    preferences: UserPreferencesUpdate,
    db: Session = Depends(get_db),
    # user_id: UUID = Depends(get_current_user)  # TODO: Add authentication
):
    """Update user preferences."""
    # TODO: Get user_id from authenticated user
    user_id = UUID("00000000-0000-0000-0000-000000000001")  # Placeholder
    
    # Get existing preferences
    db_preferences = db.query(UserPreferences).filter(
        UserPreferences.user_id == user_id
    ).first()
    
    if not db_preferences:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preferences not found. Use POST to create."
        )
    
    # Update fields
    update_data = preferences.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "location_preferences" and value is not None:
            if hasattr(value, "dict"):
                value = value.dict()
            setattr(db_preferences, field, value)
        else:
            setattr(db_preferences, field, value)
    
    db.commit()
    db.refresh(db_preferences)
    
    # Invalidate cache
    cache = get_redis_cache()
    cache.delete(_get_cache_key(user_id))
    
    logger.info(f"Preferences updated for user {user_id}")
    
    return UserPreferencesResponse(
        preferences_id=db_preferences.preferences_id,
        user_id=db_preferences.user_id,
        visa_status=db_preferences.visa_status,
        location_preferences=db_preferences.location_preferences,
        disability_status=db_preferences.disability_status,
        disability_accommodations=db_preferences.disability_accommodations,
        salary_min_usd=db_preferences.salary_min_usd,
        salary_max_usd=db_preferences.salary_max_usd,
        company_size_preferences=db_preferences.company_size_preferences,
        industry_preferences=db_preferences.industry_preferences,
        work_authorization=db_preferences.work_authorization,
        other_constraints=db_preferences.other_constraints,
        is_ready=db_preferences.is_ready,
        created_at=db_preferences.created_at.isoformat(),
        updated_at=db_preferences.updated_at.isoformat()
    )
