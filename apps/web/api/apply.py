"""Apply bot API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Dict, Any
from datetime import datetime
import uuid

from packages.database.connection import get_db
from packages.database.models import (
    JobRaw, JobScore, Application, Artifact,
    UserProfile, UserPreferences, User,
)
from services.apply_bot.apply_orchestrator import ApplyOrchestrator
from services.apply_bot.auto_submit_gate import AutoSubmitGate
from packages.common.logging import get_logger
from apps.web.auth import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["apply"])

auto_submit_gate = AutoSubmitGate()


@router.post("/{job_id}/apply/assisted/start")
async def start_assisted_apply(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start an assisted apply session for a job.
    Opens the job URL in a visible browser, fills in known fields,
    uploads the tailored resume, and STOPS before the final submit button.
    Human must review and submit manually.

    Prerequisites: job must be scored + artifacts must be generated first.
    """
    # Get job
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Require score to exist
    score = db.query(JobScore).filter(
        JobScore.job_id == job_id, JobScore.user_id == user_id
    ).first()
    if not score:
        raise HTTPException(
            status_code=400,
            detail="Job must be scored first. Call POST /jobs/{job_id}/score",
        )

    # Get user profile
    user_profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not user_profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    # Get user details
    user = db.query(User).filter(User.user_id == user_id).first()

    # Get generated artifacts
    artifacts_db = db.query(Artifact).filter(
        Artifact.job_id == job_id, Artifact.user_id == user_id
    ).all()

    if not artifacts_db:
        raise HTTPException(
            status_code=400,
            detail="Artifacts not generated. Call POST /jobs/{job_id}/artifacts/generate first.",
        )

    # Build artifacts dict — pitch is stored inline, resume needs blob path
    artifacts: Dict[str, Any] = {}
    for art in artifacts_db:
        artifacts[art.artifact_type] = art.artifact_metadata or {}

    # User data for form filling
    user_data = {
        "user_id": str(user_id),
        "email": user.email if user else "",
        "full_name": user.full_name if user else "",
        "first_name": (user.full_name or "").split()[0] if user and user.full_name else "",
        "last_name": " ".join((user.full_name or "").split()[1:]) if user and user.full_name else "",
    }

    session_id = str(uuid.uuid4())

    # Check auto-submit eligibility
    user_preferences = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    can_auto_submit, reason = auto_submit_gate.check(
        score=score.total_score,
        verdict=score.verdict,
        job_url=str(job.source_url),
        user_preferences=user_preferences,
    ) if user_preferences else (False, "No preferences set")

    # Always stop before submit — safety default
    stop_before_submit = True

    try:
        orchestrator = ApplyOrchestrator()
        result = orchestrator.start_apply_session(
            job_url=str(job.source_url),
            session_id=session_id,
            user_data=user_data,
            artifacts=artifacts,
        )

        # Create application record
        application = Application(
            job_id=job_id,
            user_id=user_id,
            apply_mode="assisted",
            status="started",
            notes=f"session_id:{session_id}",
        )
        db.add(application)
        db.commit()
        db.refresh(application)

        return {
            "application_id": str(application.application_id),
            "session_id": session_id,
            "status": result.get("status", "READY_FOR_REVIEW"),
            "platform": result.get("platform", "unknown"),
            "events": result.get("events", []),
            "auto_submit_eligible": can_auto_submit,
            "auto_submit_reason": reason,
            "message": "Browser opened and form pre-filled. Please review and submit manually.",
        }

    except Exception as e:
        logger.error(f"Assisted apply failed for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Apply session failed: {str(e)}")


@router.post("/{job_id}/apply/submit")
async def submit_application(
    job_id: UUID,
    confirmed_by_human: bool = True,
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark application as submitted after human manually submits."""
    if not confirmed_by_human:
        raise HTTPException(status_code=400, detail="Human confirmation required")

    application = db.query(Application).filter(
        Application.job_id == job_id,
        Application.user_id == user_id,
        Application.status == "started",
    ).first()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found or already submitted")

    application.status = "submitted"
    application.submitted_at = datetime.utcnow()
    db.commit()

    logger.info(f"Application submitted: job={job_id} user={user_id}")

    return {
        "application_id": str(application.application_id),
        "status": "SUBMITTED",
        "submitted_at": application.submitted_at.isoformat(),
        "next_step": f"Track outcome at POST /applications/{application.application_id}/outcome",
    }


@router.post("/{job_id}/apply/cancel")
async def cancel_application(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel an in-progress apply session."""
    application = db.query(Application).filter(
        Application.job_id == job_id,
        Application.user_id == user_id,
        Application.status == "started",
    ).first()

    if application:
        application.status = "cancelled"
        db.commit()

    return {"message": "Application cancelled"}


@router.get("/{job_id}/apply/status")
async def get_apply_status(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get application status for a job."""
    application = db.query(Application).filter(
        Application.job_id == job_id,
        Application.user_id == user_id,
    ).order_by(Application.created_at.desc()).first()

    if not application:
        return {"status": "NOT_STARTED"}

    return {
        "application_id": str(application.application_id),
        "status": application.status,
        "apply_mode": application.apply_mode,
        "submitted_at": application.submitted_at.isoformat() if application.submitted_at else None,
        "created_at": application.created_at.isoformat(),
    }
