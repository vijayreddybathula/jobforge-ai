"""Job ingestion Celery tasks."""

from celery import shared_task
from uuid import UUID
from services.job_ingestion.ingestion_service import IngestionService
from services.job_ingestion.sources.linkedin_scraper import LinkedInScraper
from packages.common.logging import get_logger

logger = get_logger(__name__)

ingestion_service = IngestionService()
linkedin_scraper = LinkedInScraper()


@shared_task(name="ingest_job")
def ingest_job_task(
    source: str, source_url: str, title: str, company: str, location: str, description: str
):
    """Celery task to ingest a job."""
    from packages.database.connection import get_db

    db = next(get_db())

    try:
        result = ingestion_service.ingest_job(
            source=source,
            source_url=source_url,
            title=title,
            company=company,
            location=location,
            description=description,
            db=db,
        )
        return result
    except Exception as e:
        logger.error(f"Job ingestion task failed: {e}")
        raise


@shared_task(name="ingest_from_linkedin")
def ingest_from_linkedin_task(search_url: str, max_jobs: int = 10):
    """Celery task to scrape and ingest from LinkedIn."""
    from packages.database.connection import get_db

    db = next(get_db())

    try:
        # Scrape jobs
        jobs = linkedin_scraper.scrape_search_results(search_url, max_jobs)

        if not jobs:
            return {"ingested": 0, "message": "No jobs found"}

        # Ingest jobs
        result = ingestion_service.ingest_batch(jobs=jobs, source="linkedin", db=db)

        return result
    except Exception as e:
        logger.error(f"LinkedIn ingestion task failed: {e}")
        raise
