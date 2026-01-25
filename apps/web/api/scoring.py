"""Scoring API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from packages.database.connection import get_db
from packages.database.models import JobRaw, JobParsed, UserProfile, UserPreferences, JobScore
from services.scoring.rules_engine import RulesEngine
from services.scoring.scoring_service import ScoringService
from packages.common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["scoring"])

rules_engine = RulesEngine()
scoring_service = ScoringService()


@router.post("/{job_id}/score")
async def score_job(
    job_id: UUID, user_id: UUID, db: Session = Depends(get_db)  # TODO: Get from authenticated user
):
    """Score job fit for user."""
    # Get job and parsed JD
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    parsed = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    if not parsed or parsed.parse_status != "PARSED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job not parsed. Call POST /parse first.",
        )

    # Get user profile and preferences
    user_profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not user_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")

    user_preferences = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not user_preferences:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User preferences not found"
        )

    # Check hard constraints first
    from packages.schemas.jd_schema import ParsedJD

    parsed_jd = ParsedJD(**parsed.parsed_json)

    is_allowed, rejection_reason = rules_engine.check_constraints(parsed_jd, user_preferences)
    if not is_allowed:
        return {
            "job_id": job_id,
            "total_score": 0,
            "verdict": "REJECTED",
            "rationale": rejection_reason,
        }

    # Score job
    result = scoring_service.score_job(
        job_id=job_id,
        user_id=user_id,
        parsed_jd=parsed_jd,
        user_profile=user_profile,
        user_preferences=user_preferences,
        db=db,
    )

    return result


@router.get("/{job_id}/score")
async def get_score(
    job_id: UUID, user_id: UUID, db: Session = Depends(get_db)  # TODO: Get from authenticated user
):
    """Get score for job."""
    score = (
        db.query(JobScore).filter(JobScore.job_id == job_id, JobScore.user_id == user_id).first()
    )

    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Score not found. Call POST /score first."
        )

    return {
        "job_id": score.job_id,
        "user_id": score.user_id,
        "total_score": score.total_score,
        "breakdown": score.breakdown,
        "verdict": score.verdict,
        "rationale": score.rationale,
        "created_at": score.created_at.isoformat(),
    }
