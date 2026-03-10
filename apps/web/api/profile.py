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

    Reads from resume.parsed_data which is populated by POST /resume/analyze.
    Keys present: core_skills, technologies, current_role, years_of_experience,
                  industry_domain, seniority_level.

    Skills are merged and categorized into buckets for the scoring engine.
    _flatten_user_skills() in scoring_service merges all buckets back into a
    flat list for matching, so the bucket names are labels only — they don't
    affect scoring accuracy.
    """
    resume = db.query(Resume).filter(
        Resume.resume_id == resume_id,
        Resume.user_id == user_id,
    ).first()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")

    # ── Core roles: confirmed > all suggested ─────────────────────────────────
    role_matches = db.query(RoleMatch).filter(RoleMatch.resume_id == resume_id).all()
    confirmed_roles = [r.role_title for r in role_matches if r.is_confirmed]
    all_roles       = [r.role_title for r in role_matches]
    core_roles      = confirmed_roles if confirmed_roles else all_roles

    # ── Skills from LLM analysis stored by POST /resume/analyze ──────────────
    parsed_data  = resume.parsed_data or {}
    core_skills  = parsed_data.get("core_skills",  [])   # e.g. ["Python", "RAG", ...]
    technologies = parsed_data.get("technologies", [])   # e.g. ["LangChain", "FastAPI", ...]

    # Deduplicate across both lists
    all_skills = list({s for s in (core_skills + technologies) if s})

    if not all_skills:
        logger.warning(
            f"build_profile_from_resume: no skills found in resume.parsed_data for {resume_id}. "
            "Did you call POST /resume/analyze first?"
        )

    # ── Categorize into labelled buckets ─────────────────────────────────────
    # Buckets are cosmetic labels — scoring flattens them all back into one list.
    # Any skill not matched goes into 'other'; non-tech users will have most
    # of their skills there, which is fine.
    skill_keywords: Dict[str, List[str]] = {
        "languages":  ["python", "java", "typescript", "javascript", "go", "rust",
                       "c++", "scala", "ruby", "swift", "kotlin", "r"],
        "frameworks": ["fastapi", "springboot", "react", "langchain", "langgraph",
                       "pydantic", "asyncio", "flask", "django", "express", "nextjs",
                       "angular", "vue"],
        "genai":      ["azure openai", "openai", "gpt-4", "gpt", "rag", "llm",
                       "embeddings", "vector", "assistants api", "responses api",
                       "multi-agent", "pgvector", "prompt", "fine-tun",
                       "hugging face", "transformers", "semantic kernel"],
        "infra":      ["docker", "kubernetes", "redis", "celery", "github actions",
                       "ci/cd", "azure", "aws", "gcp", "kafka", "elasticsearch",
                       "terraform", "ansible", "jenkins"],
        "data":       ["postgresql", "pgvector", "mysql", "mongodb", "cosmosdb",
                       "aws rds", "azure blob", "snowflake", "databricks", "spark",
                       "pandas", "numpy", "sql"],
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

    # Remove empty buckets to keep the profile clean
    categorized = {k: v for k, v in categorized.items() if v}

    # ── Upsert UserProfile ────────────────────────────────────────────────────
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile:
        profile.core_roles = core_roles
        profile.skills     = categorized
        db.commit()
        db.refresh(profile)
        logger.info(
            f"Profile updated from resume {resume_id}: "
            f"{len(core_roles)} roles, {len(all_skills)} skills"
        )
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
        logger.info(
            f"Profile built from resume {resume_id}: "
            f"{len(core_roles)} roles, {len(all_skills)} skills"
        )

    return UserProfileResponse(
        profile_id=profile.profile_id,
        user_id=profile.user_id,
        core_roles=profile.core_roles or [],
        skills=profile.skills or {},
        approved_bullets=profile.approved_bullets or [],
    )
