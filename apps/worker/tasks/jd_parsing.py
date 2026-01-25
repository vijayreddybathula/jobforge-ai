"""JD parsing Celery tasks."""

from celery import shared_task
from uuid import UUID
from services.jd_parser.jd_parser import JDParser
from packages.common.logging import get_logger

logger = get_logger(__name__)

jd_parser = JDParser()


@shared_task(name="parse_job")
def parse_job_task(job_id: UUID):
    """Celery task to parse a job description."""
    from packages.database.connection import get_db
    from packages.database.models import JobRaw, JobParsed
    from packages.schemas.jd_schema import ParsedJD

    db = next(get_db())

    try:
        # Get job
        job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Parse
        parsed_jd = jd_parser.parse(job.text_content)

        # Save to database
        job_parsed = JobParsed(
            job_id=job_id,
            parsed_json=parsed_jd.dict(),
            parser_version="jd-parser-v1",
            parse_status="PARSED",
        )

        db.add(job_parsed)
        db.commit()

        logger.info(f"Job parsed: {job_id}")

        return {"job_id": str(job_id), "parse_status": "PARSED"}
    except Exception as e:
        logger.error(f"JD parsing task failed: {e}")
        raise
