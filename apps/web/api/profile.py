"""User profile API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from packages.database.connection import get_db
from packages.database.models import UserProfile, Resume, RoleMatch
from packages.common.logging import get_logger
from apps.web.auth import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


class UserProfileCreate(BaseModel):
    core_roles: List[str] = []
    skills: Dict[str, Any] = {}
    approved_bullets: List[str] = []


class UserProfileResponse(BaseModel):
    profile_id: UUID
    user_id: UUID
    core_roles: Optional[List[str]] = []
    skills: Optional[Dict[str, Any]] = {}
    approved_bullets: Optional[List[str]] = []


@router.get("", response_model=UserProfileResponse)
async def get_profile(
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user profile."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Upload and analyze a resume first, or POST /profile to create manually.",
        )
    return UserProfileResponse(
        profile_id=profile.profile_id,
        user_id=profile.user_id,
        core_roles=profile.core_roles or [],
        skills=profile.skills or {},
        approved_bullets=profile.approved_bullets or [],
    )


@router.post("", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    body: UserProfileCreate,
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually create user profile."""
    existing = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile already exists. Use PUT to update.",
        )
    profile = UserProfile(
        user_id=user_id,
        core_roles=body.core_roles,
        skills=body.skills,
        approved_bullets=body.approved_bullets,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    logger.info(f"Profile created for user {user_id}")
    return UserProfileResponse(
        profile_id=profile.profile_id,
        user_id=profile.user_id,
        core_roles=profile.core_roles or [],
        skills=profile.skills or {},
        approved_bullets=profile.approved_bullets or [],
    )


@router.put("", response_model=UserProfileResponse)
async def update_profile(
    body: UserProfileCreate,
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user profile."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    if body.core_roles:
        profile.core_roles = body.core_roles
    if body.skills:
        profile.skills = body.skills
    if body.approved_bullets:
        profile.approved_bullets = body.approved_bullets
    db.commit()
    db.refresh(profile)
    logger.info(f"Profile updated for user {user_id}")
    return UserProfileResponse(
        profile_id=profile.profile_id,
        user_id=profile.user_id,
        core_roles=profile.core_roles or [],
        skills=profile.skills or {},
        approved_bullets=profile.approved_bullets or [],
    )


@router.post("/build-from-resume/{resume_id}", response_model=UserProfileResponse)
async def build_profile_from_resume(
    resume_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Auto-build UserProfile from an analyzed resume.
    Uses LLM-extracted skills + confirmed role matches already in DB.
    Call this after POST /resume/analyze/{resume_id}.
    """
    # Get resume
    resume = db.query(Resume).filter(
        Resume.resume_id == resume_id,
        Resume.user_id == user_id
    ).first()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")

    # Get confirmed role matches (fall back to all suggested if none confirmed)
    role_matches = db.query(RoleMatch).filter(RoleMatch.resume_id == resume_id).all()
    confirmed_roles = [r.role_title for r in role_matches if r.is_confirmed]
    all_roles = [r.role_title for r in role_matches]
    core_roles = confirmed_roles if confirmed_roles else all_roles

    # Extract skills from parsed_data stored during upload
    parsed_data = resume.parsed_data or {}
    raw_skills = parsed_data.get("skills", [])

    # Also pull from LLM analysis if stored (set by role_extractor in analyze step)
    # parsed_data may contain: core_skills, technologies from the LLM response
    core_skills = parsed_data.get("core_skills", [])
    technologies = parsed_data.get("technologies", [])

    # Merge and categorize skills
    all_skills = list(set(raw_skills + core_skills + technologies))

    # Categorize into known buckets for scoring engine
    skill_keywords = {
        "languages": ["python", "java", "typescript", "javascript", "go", "rust", "c++", "scala"],
        "frameworks": ["fastapi", "springboot", "react", "langchain", "langgraph", "pydantic", "asyncio"],
        "genai": ["azure openai", "openai", "gpt-4", "rag", "llm", "embeddings", "vector", "assistants api",
                  "responses api", "multi-agent", "pgvector", "pdfplumber", "prompt"],
        "infra": ["docker", "kubernetes", "redis", "celery", "github actions", "ci/cd", "azure", "aws",
                  "kafka", "elasticsearch", "apim", "sonarqube"],
        "data": ["postgresql", "pgvector", "mysql", "mongodb", "cosmosdb", "aws rds", "azure blob"],
    }

    categorized: Dict[str, List[str]] = {k: [] for k in skill_keywords}
    uncategorized: List[str] = []

    for skill in all_skills:
        skill_lower = skill.lower()
        matched = False
        for category, keywords in skill_keywords.items():
            if any(kw in skill_lower for kw in keywords):
                categorized[category].append(skill)
                matched = True
                break
        if not matched:
            uncategorized.append(skill)

    if uncategorized:
        categorized["other"] = uncategorized

    # Upsert UserProfile
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile:
        profile.core_roles = core_roles
        profile.skills = categorized
        db.commit()
        db.refresh(profile)
        logger.info(f"Profile updated from resume {resume_id} for user {user_id}")
    else:
        profile = UserProfile(
            user_id=user_id,
            core_roles=core_roles,
            skills=categorized,
            approved_bullets=[],
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        logger.info(f"Profile built from resume {resume_id} for user {user_id}")

    return UserProfileResponse(
        profile_id=profile.profile_id,
        user_id=profile.user_id,
        core_roles=profile.core_roles or [],
        skills=profile.skills or {},
        approved_bullets=profile.approved_bullets or [],
    )
