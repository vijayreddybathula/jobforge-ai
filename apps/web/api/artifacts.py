"""Artifacts API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from packages.database.connection import get_db
from packages.database.models import JobRaw, JobParsed, UserProfile, UserPreferences, Artifact, JobScore
from services.artifacts.resume_tailor import ResumeTailor
from services.artifacts.pitch_generator import PitchGenerator
from services.artifacts.answers_generator import AnswersGenerator
from packages.schemas.jd_schema import ParsedJD
from packages.common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["artifacts"])

resume_tailor = ResumeTailor()
pitch_generator = PitchGenerator()
answers_generator = AnswersGenerator()


@router.post("/{job_id}/artifacts/generate")
async def generate_artifacts(
    job_id: UUID,
    user_id: UUID,  # TODO: Get from authenticated user
    artifact_types: List[str],  # ["resume", "pitch", "answers"]
    db: Session = Depends(get_db)
):
    """Generate artifacts for job application."""
    # Get job and parsed JD
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    parsed = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    if not parsed or parsed.parse_status != "PARSED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job not parsed"
        )
    
    # Get user profile
    user_profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    user_preferences = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    
    parsed_jd = ParsedJD(**parsed.parsed_json)
    
    artifacts = []
    
    # Generate requested artifacts
    for artifact_type in artifact_types:
        if artifact_type == "resume":
            # Get base resume (simplified - in production, get from user's resumes)
            base_resume_path = "./storage/resumes/base.pdf"  # Placeholder
            
            result = resume_tailor.tailor_resume(
                base_resume_path=base_resume_path,
                parsed_jd=parsed_jd,
                user_skills=user_profile.skills or {},
                output_path=f"./storage/artifacts/{job_id}_{user_id}_resume.pdf"
            )
            
            artifact = Artifact(
                job_id=job_id,
                user_id=user_id,
                artifact_type="resume",
                path=result["output_path"],
                metadata=result
            )
            db.add(artifact)
            artifacts.append({
                "type": "resume",
                "path": result["output_path"],
                "metadata": result
            })
        
        elif artifact_type == "pitch":
            # Get score for pitch generation
            score = db.query(JobScore).filter(
                JobScore.job_id == job_id,
                JobScore.user_id == user_id
            ).first()
            
            score_value = score.total_score if score else 75
            
            pitch = pitch_generator.generate(
                parsed_jd=parsed_jd,
                user_skills=user_profile.skills or {},
                score=score_value
            )
            
            # Save pitch
            pitch_path = f"./storage/artifacts/{job_id}_{user_id}_pitch.txt"
            from pathlib import Path
            Path(pitch_path).parent.mkdir(parents=True, exist_ok=True)
            Path(pitch_path).write_text(pitch)
            
            artifact = Artifact(
                job_id=job_id,
                user_id=user_id,
                artifact_type="pitch",
                path=pitch_path,
                metadata={"length": len(pitch)}
            )
            db.add(artifact)
            artifacts.append({
                "type": "pitch",
                "path": pitch_path,
                "metadata": {"length": len(pitch)}
            })
        
        elif artifact_type == "answers":
            # Generate answers for common questions
            user_data = {
                "years_of_experience": 5,  # TODO: Extract from profile
                "salary_min_usd": user_preferences.salary_min_usd if user_preferences else None,
                "visa_status": user_preferences.visa_status if user_preferences else "",
                "location_preferences": user_preferences.location_preferences if user_preferences else {}
            }
            
            answers = {}
            for question_key, question_text in AnswersGenerator.COMMON_QUESTIONS.items():
                answers[question_key] = answers_generator.generate_answer(question_text, user_data)
            
            # Save answers
            answers_path = f"./storage/artifacts/{job_id}_{user_id}_answers.json"
            from pathlib import Path
            import json
            Path(answers_path).parent.mkdir(parents=True, exist_ok=True)
            Path(answers_path).write_text(json.dumps(answers, indent=2))
            
            artifact = Artifact(
                job_id=job_id,
                user_id=user_id,
                artifact_type="answers",
                path=answers_path,
                metadata={"questions_count": len(answers)}
            )
            db.add(artifact)
            artifacts.append({
                "type": "answers",
                "path": answers_path,
                "metadata": {"questions_count": len(answers)}
            })
    
    db.commit()
    
    logger.info(f"Artifacts generated for job {job_id}: {artifact_types}")
    
    return {
        "job_id": job_id,
        "artifacts": artifacts
    }


@router.get("/{job_id}/artifacts")
async def list_artifacts(
    job_id: UUID,
    user_id: UUID,  # TODO: Get from authenticated user
    db: Session = Depends(get_db)
):
    """List artifacts for job."""
    artifacts = db.query(Artifact).filter(
        Artifact.job_id == job_id,
        Artifact.user_id == user_id
    ).all()
    
    return [
        {
            "artifact_id": str(a.artifact_id),
            "type": a.artifact_type,
            "path": a.path,
            "metadata": a.metadata,
            "created_at": a.created_at.isoformat()
        }
        for a in artifacts
    ]


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: UUID,
    db: Session = Depends(get_db)
):
    """Download artifact file."""
    artifact = db.query(Artifact).filter(Artifact.artifact_id == artifact_id).first()
    
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    
    from pathlib import Path
    file_path = Path(artifact.path)
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact file not found"
        )
    
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream"
    )
