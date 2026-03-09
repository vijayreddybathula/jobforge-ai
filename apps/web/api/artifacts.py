"""Artifacts API — user_id from auth."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from packages.database.connection import get_db
from packages.database.models import JobRaw, JobParsed, Resume, UserProfile, Artifact
from services.artifacts.pitch_generator import PitchGenerator
from services.artifacts.resume_tailor import ResumeTailor
from services.artifacts.answers_generator import AnswersGenerator
from apps.web.auth import get_current_user
from packages.common.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["artifacts"])

pitch_gen = PitchGenerator()
resume_tailor = ResumeTailor()
answers_gen = AnswersGenerator()

ARTIFACT_TYPES = {"pitch", "resume", "answers"}


@router.post("/{job_id}/artifacts/generate")
async def generate_artifacts(
    job_id: UUID,
    artifact_types: List[str] = Query(default=["pitch", "resume", "answers"]),
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate application artifacts for the authenticated user.
    Uses the user's own resume + profile. Completely isolated per user.
    """
    invalid = set(artifact_types) - ARTIFACT_TYPES
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown artifact types: {invalid}")

    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    parsed = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    if not parsed or parsed.parse_status != "PARSED":
        raise HTTPException(status_code=400, detail="Job must be parsed first.")

    # Get the user's most recent resume
    resume = (
        db.query(Resume)
        .filter(Resume.user_id == current_user_id)
        .order_by(Resume.created_at.desc())
        .first()
    )
    if not resume or not resume.parsed_data:
        raise HTTPException(
            status_code=404,
            detail="No parsed resume found. Upload and analyze a resume first.",
        )

    user_profile = db.query(UserProfile).filter(UserProfile.user_id == current_user_id).first()
    if not user_profile:
        raise HTTPException(status_code=404, detail="User profile not found.")

    from packages.schemas.jd_schema import ParsedJD
    parsed_jd = ParsedJD(**parsed.parsed_json)

    resume_text = str(resume.parsed_data)
    user_profile_dict = {
        "core_roles": user_profile.core_roles,
        "skills": user_profile.skills,
    }

    artifacts = {}
    errors = {}

    if "pitch" in artifact_types:
        try:
            pitch = pitch_gen.generate_pitch(
                resume_text=resume_text,
                parsed_jd=parsed_jd,
                user_profile=user_profile_dict,
            )
            artifacts["pitch"] = pitch
            _upsert_artifact(db, job_id, current_user_id, "pitch", {"content": pitch})
        except Exception as e:
            errors["pitch"] = str(e)

    if "resume" in artifact_types:
        try:
            tailored = resume_tailor.tailor_resume(
                resume_text=resume_text,
                parsed_jd=parsed_jd,
                user_profile=user_profile_dict,
            )
            artifacts["resume"] = tailored
            _upsert_artifact(db, job_id, current_user_id, "resume", tailored)
        except Exception as e:
            errors["resume"] = str(e)

    if "answers" in artifact_types:
        try:
            answers = answers_gen.generate_answers(
                resume_text=resume_text,
                parsed_jd=parsed_jd,
                user_profile=user_profile_dict,
            )
            artifacts["answers"] = answers
            _upsert_artifact(db, job_id, current_user_id, "answers", {"content": answers})
        except Exception as e:
            errors["answers"] = str(e)

    return {
        "job_id": str(job_id),
        "user_id": str(current_user_id),
        "artifacts": artifacts,
        "errors": errors if errors else None,
    }


@router.get("/{job_id}/artifacts")
async def get_artifacts(
    job_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get previously generated artifacts for this user + job."""
    arts = (
        db.query(Artifact)
        .filter(Artifact.job_id == job_id, Artifact.user_id == current_user_id)
        .all()
    )
    if not arts:
        return {"job_id": str(job_id), "artifacts": {}, "message": "No artifacts yet. Call POST .../generate"}

    return {
        "job_id": str(job_id),
        "user_id": str(current_user_id),
        "artifacts": {a.artifact_type: a.artifact_metadata for a in arts},
        "generated_at": max(a.created_at for a in arts).isoformat(),
    }


def _upsert_artifact(db, job_id, user_id, artifact_type, metadata):
    existing = (
        db.query(Artifact)
        .filter(
            Artifact.job_id == job_id,
            Artifact.user_id == user_id,
            Artifact.artifact_type == artifact_type,
        )
        .first()
    )
    if existing:
        existing.artifact_metadata = metadata
        existing.path = f"inline:{job_id}:{artifact_type}"
    else:
        db.add(Artifact(
            job_id=job_id,
            user_id=user_id,
            artifact_type=artifact_type,
            path=f"inline:{job_id}:{artifact_type}",
            artifact_metadata=metadata,
        ))
    db.commit()
