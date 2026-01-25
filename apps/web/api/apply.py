"""Apply bot API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Dict, Any

from packages.database.connection import get_db
from packages.database.models import (
    JobRaw,
    JobScore,
    Application,
    Artifact,
    UserProfile,
    UserPreferences,
)
from services.apply_bot.apply_orchestrator import ApplyOrchestrator
from services.apply_bot.auto_submit_gate import AutoSubmitGate
from packages.common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["apply"])

apply_orchestrator = ApplyOrchestrator()
auto_submit_gate = AutoSubmitGate()


@router.post("/{job_id}/apply/assisted/start")
async def start_assisted_apply(
    job_id: UUID, user_id: UUID, db: Session = Depends(get_db)  # TODO: Get from authenticated user
):
    """Start assisted apply session."""
    # Get job
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Get user profile and preferences
    user_profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    user_preferences = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()

    if not user_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")

    # Get artifacts
    artifacts_db = (
        db.query(Artifact).filter(Artifact.job_id == job_id, Artifact.user_id == user_id).all()
    )

    artifacts = {}
    for art in artifacts_db:
        if art.artifact_type == "resume":
            artifacts["resume_path"] = art.path
        elif art.artifact_type == "pitch":
            from pathlib import Path

            artifacts["pitch"] = Path(art.path).read_text() if Path(art.path).exists() else ""
        elif art.artifact_type == "answers":
            artifacts["answers"] = art.path

    # Prepare user data
    user_data = {
        "user_id": user_id,
        "email": "user@example.com",  # TODO: Get from user model
        "first_name": "John",  # TODO: Get from user model
        "last_name": "Doe",  # TODO: Get from user model
    }

    # Generate session ID
    import uuid

    session_id = str(uuid.uuid4())

    # Start apply session
    try:
        result = apply_orchestrator.start_apply_session(
            job_url=job.source_url, session_id=session_id, user_data=user_data, artifacts=artifacts
        )

        # Create application record
        application = Application(
            job_id=job_id, user_id=user_id, apply_mode="assisted", status="started"
        )
        db.add(application)
        db.commit()

        return result

    except Exception as e:
        logger.error(f"Assisted apply failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start apply session: {str(e)}",
        )


@router.post("/{job_id}/apply/submit")
async def submit_application(
    job_id: UUID,
    user_id: UUID,  # TODO: Get from authenticated user
    confirmed_by_human: bool = True,
    db: Session = Depends(get_db),
):
    """Submit application (after human review)."""
    if not confirmed_by_human:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Human confirmation required"
        )

    # Get application
    application = (
        db.query(Application)
        .filter(
            Application.job_id == job_id,
            Application.user_id == user_id,
            Application.status == "started",
        )
        .first()
    )

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found or already submitted",
        )

    # Update application status
    from datetime import datetime

    application.status = "submitted"
    application.submitted_at = datetime.utcnow()
    db.commit()

    logger.info(f"Application submitted: {job_id} by user {user_id}")

    return {
        "application_id": application.application_id,
        "status": "SUBMITTED",
        "submitted_at": application.submitted_at.isoformat(),
    }


@router.post("/{job_id}/apply/cancel")
async def cancel_application(
    job_id: UUID, user_id: UUID, db: Session = Depends(get_db)  # TODO: Get from authenticated user
):
    """Cancel application session."""
    application = (
        db.query(Application)
        .filter(
            Application.job_id == job_id,
            Application.user_id == user_id,
            Application.status == "started",
        )
        .first()
    )

    if application:
        application.status = "cancelled"
        db.commit()

    return {"message": "Application cancelled"}
