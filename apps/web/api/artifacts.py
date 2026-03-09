"""Artifacts API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional

from packages.database.connection import get_db
from packages.database.models import (
    JobRaw, JobParsed, UserProfile, UserPreferences, Artifact, JobScore, Resume,
)
from services.artifacts.resume_tailor import ResumeTailor
from services.artifacts.pitch_generator import PitchGenerator
from services.artifacts.answers_generator import AnswersGenerator
from packages.schemas.jd_schema import ParsedJD
from packages.common.logging import get_logger
from apps.web.auth import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["artifacts"])

resume_tailor = ResumeTailor()
pitch_generator = PitchGenerator()
answers_generator = AnswersGenerator()


@router.post("/{job_id}/artifacts/generate")
async def generate_artifacts(
    job_id: UUID,
    artifact_types: List[str] = Query(default=["pitch", "resume", "answers"], description="Types to generate: pitch, resume, answers"),
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate AI-powered artifacts for a job application.
    - pitch: 3-5 sentence personalized recruiter pitch
    - resume: Tailored bullet points + ATS-optimized summary
    - answers: Answers to common application questions

    Returns all generated content inline (no filesystem dependency).
    """
    # Get job
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Get parsed JD
    parsed = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    if not parsed or parsed.parse_status != "PARSED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job not parsed. Call POST /jobs/{job_id}/parse first.",
        )

    # Get user profile
    user_profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found. Call POST /profile/build-from-resume/{resume_id} first.",
        )

    # Get user preferences
    user_preferences = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    preferences_dict = {}
    if user_preferences:
        preferences_dict = {
            "salary_min_usd": user_preferences.salary_min_usd,
            "salary_max_usd": user_preferences.salary_max_usd,
            "visa_status": user_preferences.visa_status,
            "location_preferences": user_preferences.location_preferences,
        }

    # Get resume text from most recent resume
    resume = db.query(Resume).filter(Resume.user_id == user_id).order_by(Resume.created_at.desc()).first()
    resume_text = ""
    if resume and resume.parsed_data:
        resume_text = resume.parsed_data.get("text_content", "")

    parsed_jd = ParsedJD(**parsed.parsed_json)
    profile_dict = {
        "core_roles": user_profile.core_roles or [],
        "skills": user_profile.skills or {},
    }

    # Get score for pitch
    score_record = db.query(JobScore).filter(
        JobScore.job_id == job_id, JobScore.user_id == user_id
    ).first()
    score_value = score_record.total_score if score_record else 75

    generated = {}
    saved_artifacts = []

    for artifact_type in artifact_types:
        try:
            if artifact_type == "pitch":
                content = pitch_generator.generate(
                    parsed_jd=parsed_jd,
                    user_profile=profile_dict,
                    resume_text=resume_text,
                    score=score_value,
                )
                generated["pitch"] = content
                artifact_meta = {"length": len(content)}

            elif artifact_type == "resume":
                content = resume_tailor.tailor_resume(
                    resume_text=resume_text,
                    parsed_jd=parsed_jd,
                    user_profile=profile_dict,
                )
                generated["resume"] = content
                artifact_meta = {
                    "bullets_count": len(content.get("bullets", [])),
                    "keywords_count": len(content.get("keywords_incorporated", [])),
                }

            elif artifact_type == "answers":
                content = answers_generator.generate_answers(
                    parsed_jd=parsed_jd,
                    user_profile=profile_dict,
                    user_preferences=preferences_dict,
                    resume_text=resume_text,
                )
                generated["answers"] = content
                artifact_meta = {"questions_count": len(content)}

            else:
                logger.warning(f"Unknown artifact type: {artifact_type}")
                continue

            # Save artifact record to DB (content stored inline, no filesystem)
            artifact = Artifact(
                job_id=job_id,
                user_id=user_id,
                artifact_type=artifact_type,
                path=f"inline:{job_id}:{artifact_type}",  # marker for inline storage
                artifact_metadata=artifact_meta,
            )
            db.add(artifact)
            saved_artifacts.append(artifact_type)

        except Exception as e:
            logger.error(f"Failed to generate {artifact_type} artifact: {e}")
            generated[f"{artifact_type}_error"] = str(e)

    db.commit()
    logger.info(f"Artifacts generated for job {job_id}: {saved_artifacts}")

    return {
        "job_id": str(job_id),
        "user_id": str(user_id),
        "score": score_value,
        "artifacts": generated,
    }


@router.get("/{job_id}/artifacts")
async def list_artifacts(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List artifact records for a job."""
    artifacts = db.query(Artifact).filter(
        Artifact.job_id == job_id, Artifact.user_id == user_id
    ).all()

    return [
        {
            "artifact_id": str(a.artifact_id),
            "type": a.artifact_type,
            "metadata": a.artifact_metadata,
            "created_at": a.created_at.isoformat(),
        }
        for a in artifacts
    ]
