"""Apply API — assisted apply records + context endpoint."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime

from packages.database.connection import get_db
from packages.database.models import (
    JobRaw, JobParsed, JobScore, Application, Artifact,
    UserProfile, UserPreferences, User,
)
from packages.common.logging import get_logger
from apps.web.auth import get_current_user

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["apply"])


@router.get("/{job_id}/apply/context")
async def get_apply_context(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: Session   = Depends(get_db),
):
    """
    Return everything the UI needs to run an assisted-apply session:
      - The direct apply URL to open in a new tab
      - Pre-filled field values (name, email) for copy-paste
      - Tailored pitch / cover letter if artifacts exist
      - Parsed JD requirements for reference while filling the form

    No server-side browser automation.  The user applies in their own
    browser; this endpoint gives them the data to do it fast.
    """
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    score = db.query(JobScore).filter(
        JobScore.job_id == job_id, JobScore.user_id == user_id
    ).first()
    if not score:
        raise HTTPException(
            status_code=400,
            detail="Score this job first so we can tailor the apply context.",
        )

    user         = db.query(User).filter(User.user_id == user_id).first()
    user_profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    parsed       = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    artifacts_db = db.query(Artifact).filter(
        Artifact.job_id == job_id, Artifact.user_id == user_id
    ).all()

    # Best apply URL: prefer apply_link (direct ATS), fall back to source_url
    apply_url = job.apply_link or str(job.source_url)

    # Pre-filled data for the form
    full_name  = user.full_name  if user else ""
    email      = user.email      if user else ""
    first_name = full_name.split()[0]             if full_name else ""
    last_name  = " ".join(full_name.split()[1:])  if full_name else ""

    # Pitch / cover letter from artifacts if generated
    pitch = None
    for art in artifacts_db:
        if art.artifact_type == "pitch" and art.artifact_metadata:
            pitch = art.artifact_metadata.get("content") or art.artifact_metadata.get("pitch")
            break

    # Top skills from profile for the "skills" field
    skills_flat: list = []
    if user_profile and user_profile.skills:
        for bucket in user_profile.skills.values():
            if isinstance(bucket, list):
                skills_flat.extend(bucket)

    return {
        "job_id":     str(job_id),
        "apply_url":  apply_url,
        "job_title":  job.title,
        "company":    job.company,
        "score":      score.total_score,
        "verdict":    score.verdict,
        "prefill": {
            "first_name": first_name,
            "last_name":  last_name,
            "full_name":  full_name,
            "email":      email,
            "skills":     skills_flat[:20],
        },
        "pitch":             pitch,
        "parsed_jd":         parsed.parsed_json if parsed else None,
        "artifacts_ready":   len(artifacts_db) > 0,
    }


@router.post("/{job_id}/apply/start")
async def start_apply(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: Session   = Depends(get_db),
):
    """
    Record that the user has started an assisted-apply session.
    The UI calls this when the user clicks Apply — we log it so the
    pipeline shows the job as in-progress.
    """
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Idempotent: don't create a second record if already started
    existing = db.query(Application).filter(
        Application.job_id == job_id,
        Application.user_id == user_id,
        Application.status.in_(["started", "submitted"]),
    ).first()
    if existing:
        return {
            "application_id": str(existing.application_id),
            "status": existing.status,
            "message": "Application already in progress.",
        }

    application = Application(
        job_id=job_id,
        user_id=user_id,
        apply_mode="assisted",
        status="started",
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    logger.info(f"Apply started: job={job_id} user={user_id}")
    return {
        "application_id": str(application.application_id),
        "status": "started",
        "apply_url": job.apply_link or str(job.source_url),
        "message": "Application started. Open the URL and fill in the form.",
    }


@router.post("/{job_id}/apply/submit")
async def submit_application(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: Session   = Depends(get_db),
):
    """Mark application as submitted after the user clicks Submit on the employer site."""
    application = db.query(Application).filter(
        Application.job_id == job_id,
        Application.user_id == user_id,
        Application.status == "started",
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="No in-progress application found. Call /apply/start first.")

    application.status       = "submitted"
    application.submitted_at = datetime.utcnow()
    db.commit()
    logger.info(f"Application submitted: job={job_id} user={user_id}")
    return {
        "application_id": str(application.application_id),
        "status": "submitted",
        "submitted_at": application.submitted_at.isoformat(),
        "next_step": f"Track outcome at POST /applications/{application.application_id}/outcome",
    }


@router.post("/{job_id}/apply/cancel")
async def cancel_application(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: Session   = Depends(get_db),
):
    application = db.query(Application).filter(
        Application.job_id == job_id,
        Application.user_id == user_id,
        Application.status == "started",
    ).first()
    if application:
        application.status = "cancelled"
        db.commit()
    return {"message": "Application cancelled."}


@router.get("/{job_id}/apply/status")
async def get_apply_status(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: Session   = Depends(get_db),
):
    application = db.query(Application).filter(
        Application.job_id == job_id,
        Application.user_id == user_id,
    ).order_by(Application.created_at.desc()).first()
    if not application:
        return {"status": "NOT_STARTED"}
    return {
        "application_id": str(application.application_id),
        "status":         application.status,
        "apply_mode":     application.apply_mode,
        "submitted_at":   application.submitted_at.isoformat() if application.submitted_at else None,
        "created_at":     application.created_at.isoformat(),
    }
