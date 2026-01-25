"""Scoring Celery tasks."""

from celery import shared_task
from uuid import UUID
from services.scoring.scoring_service import ScoringService
from packages.common.logging import get_logger

logger = get_logger(__name__)

scoring_service = ScoringService()


@shared_task(name="score_job")
def score_job_task(job_id: UUID, user_id: UUID):
    """Celery task to score a job."""
    from packages.database.connection import get_db
    from packages.database.models import JobRaw, JobParsed, UserProfile, UserPreferences
    from packages.schemas.jd_schema import ParsedJD

    db = next(get_db())

    try:
        # Get job and parsed JD
        job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
        parsed = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
        user_profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        user_preferences = (
            db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        )

        if not all([job, parsed, user_profile, user_preferences]):
            raise ValueError("Missing required data for scoring")

        parsed_jd = ParsedJD(**parsed.parsed_json)

        # Score job
        result = scoring_service.score_job(
            job_id=job_id,
            user_id=user_id,
            parsed_jd=parsed_jd,
            user_profile=user_profile,
            user_preferences=user_preferences,
            db=db,
        )

        logger.info(f"Job scored: {job_id} -> {result['total_score']}/100")

        return result
    except Exception as e:
        logger.error(f"Scoring task failed: {e}")
        raise
