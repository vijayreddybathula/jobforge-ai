"""Scoring API endpoints — user_id from auth, not query params."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID

from packages.database.connection import get_db
from packages.database.models import JobRaw, JobParsed, UserProfile, UserPreferences, JobScore
from services.scoring.rules_engine import RulesEngine
from services.scoring.scoring_service import ScoringService
from apps.web.auth import get_current_user
from packages.common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["scoring"])

rules_engine = RulesEngine()
scoring_service = ScoringService()


@router.post("/{job_id}/score")
async def score_job(
    job_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Score this job's fit for the authenticated user.
    Uses the user's confirmed profile + preferences — completely isolated per user.
    Same job can produce different scores for different users.
    """
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    parsed = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    if not parsed or parsed.parse_status != "PARSED":
        raise HTTPException(
            status_code=400,
            detail="Job not parsed yet. Call POST /jobs/{id}/parse first.",
        )

    user_profile = db.query(UserProfile).filter(UserProfile.user_id == current_user_id).first()
    if not user_profile:
        raise HTTPException(
            status_code=404,
            detail="User profile not found. Complete resume upload and role confirmation first.",
        )

    user_preferences = (
        db.query(UserPreferences).filter(UserPreferences.user_id == current_user_id).first()
    )
    if not user_preferences:
        raise HTTPException(
            status_code=404,
            detail="User preferences not set. Complete preferences setup first.",
        )

    from packages.schemas.jd_schema import ParsedJD

    parsed_jd = ParsedJD(**parsed.parsed_json)

    is_allowed, rejection_reason = rules_engine.check_constraints(parsed_jd, user_preferences)
    if not is_allowed:
        return {
            "job_id": str(job_id),
            "user_id": str(current_user_id),
            "total_score": 0,
            "verdict": "REJECTED",
            "rationale": rejection_reason,
        }

    result = scoring_service.score_job(
        job_id=job_id,
        user_id=current_user_id,
        parsed_jd=parsed_jd,
        user_profile=user_profile,
        user_preferences=user_preferences,
        db=db,
    )
    return result


@router.get("/{job_id}/score")
async def get_score(
    job_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the authenticated user's score for this job.
    Only returns the calling user's score — never another user's.
    """
    score = (
        db.query(JobScore)
        .filter(JobScore.job_id == job_id, JobScore.user_id == current_user_id)
        .first()
    )

    if not score:
        raise HTTPException(
            status_code=404,
            detail="Score not found. Call POST /jobs/{id}/score first.",
        )

    return {
        "job_id": str(score.job_id),
        "user_id": str(score.user_id),
        "total_score": score.total_score,
        "breakdown": score.breakdown,
        "verdict": score.verdict,
        "rationale": score.rationale,
        "created_at": score.created_at.isoformat(),
    }


@router.post("/score-all")
async def score_all_jobs(
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Score all parsed, unscored jobs for the authenticated user.
    Only scores jobs the current user hasn't scored yet.
    """
    user_profile = db.query(UserProfile).filter(UserProfile.user_id == current_user_id).first()
    if not user_profile:
        raise HTTPException(status_code=404, detail="User profile not found. Set up profile first.")

    user_preferences = (
        db.query(UserPreferences).filter(UserPreferences.user_id == current_user_id).first()
    )
    if not user_preferences:
        raise HTTPException(status_code=404, detail="User preferences not set.")

    # All parsed jobs
    parsed_jobs = db.query(JobParsed).filter(JobParsed.parse_status == "PARSED").all()

    # Jobs already scored by this user
    already_scored = {
        str(s.job_id)
        for s in db.query(JobScore).filter(JobScore.user_id == current_user_id).all()
    }

    from packages.schemas.jd_schema import ParsedJD

    results = {"scored": 0, "skipped_already_scored": 0, "failed": 0, "rejected": 0}

    for parsed in parsed_jobs:
        job_id_str = str(parsed.job_id)
        if job_id_str in already_scored:
            results["skipped_already_scored"] += 1
            continue

        try:
            parsed_jd = ParsedJD(**parsed.parsed_json)
            is_allowed, reason = rules_engine.check_constraints(parsed_jd, user_preferences)
            if not is_allowed:
                results["rejected"] += 1
                continue

            scoring_service.score_job(
                job_id=parsed.job_id,
                user_id=current_user_id,
                parsed_jd=parsed_jd,
                user_profile=user_profile,
                user_preferences=user_preferences,
                db=db,
            )
            results["scored"] += 1
        except Exception as e:
            logger.error(f"score-all failed for job {parsed.job_id}: {e}")
            results["failed"] += 1

    return {
        "message": "Batch scoring complete",
        "user_id": str(current_user_id),
        **results,
    }
