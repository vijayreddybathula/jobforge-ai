"""Job ingestion service."""

from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy.orm import Session

from packages.database.models import JobRaw, IngestionSource, ScrapingSession
from packages.database.connection import get_db
from packages.common.rate_limiter import RateLimiter
from packages.common.redis_cache import get_redis_cache
from packages.common.logging import get_logger
from services.job_ingestion.normalizer import JobNormalizer

logger = get_logger(__name__)


class IngestionService:
    """Service for ingesting jobs from various sources."""
    
    def __init__(self):
        """Initialize ingestion service."""
        self.normalizer = JobNormalizer()
        self.rate_limiter = RateLimiter()
        self.cache = get_redis_cache()
    
    def ingest_job(
        self,
        source: str,
        source_url: str,
        title: str,
        company: str,
        location: str,
        description: str,
        html_content: Optional[str] = None,
        posted_at: Optional[datetime] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Ingest a single job posting.
        
        Args:
            source: Source type (linkedin, workday, etc.)
            source_url: URL of the job posting
            title: Job title
            company: Company name
            location: Job location
            description: Job description text
            html_content: Optional HTML content
            posted_at: Optional posting date
            db: Database session
        
        Returns:
            Dictionary with job_id and ingest_status
        """
        if db is None:
            db = next(get_db())
        
        try:
            # Normalize and deduplicate
            normalized = self.normalizer.normalize(
                title=title,
                company=company,
                location=location,
                description=description
            )
            
            content_hash = normalized["content_hash"]
            
            # Check if already exists (using Redis set for fast lookup)
            seen_key = f"jobs:seen:{content_hash}"
            if self.cache.is_in_set(seen_key, content_hash):
                logger.debug(f"Job already seen: {content_hash[:8]}...")
                return {
                    "job_id": None,
                    "ingest_status": "DUPLICATE",
                    "dedupe": True
                }
            
            # Check database for existing job
            existing = db.query(JobRaw).filter(
                JobRaw.content_hash == content_hash
            ).first()
            
            if existing:
                # Add to Redis set
                self.cache.add_to_set(seen_key, content_hash)
                return {
                    "job_id": existing.job_id,
                    "ingest_status": "DUPLICATE",
                    "dedupe": True
                }
            
            # Create new job record
            job = JobRaw(
                source=source,
                source_url=source_url,
                company=normalized["company"],
                title=normalized["title"],
                location=normalized["location"],
                text_content=normalized["description"],
                content_hash=content_hash,
                posted_at=posted_at,
                ingest_status="INGESTED"
            )
            
            # Save HTML snapshot if provided
            if html_content:
                from pathlib import Path
                storage_path = Path("./storage/jobs")
                storage_path.mkdir(parents=True, exist_ok=True)
                snapshot_path = storage_path / f"{content_hash}.html"
                snapshot_path.write_text(html_content, encoding="utf-8")
                job.html_snapshot_path = str(snapshot_path)
            
            db.add(job)
            db.commit()
            db.refresh(job)
            
            # Add to Redis set
            self.cache.add_to_set(seen_key, content_hash)
            
            logger.info(f"Job ingested: {job.job_id} from {source}")
            
            return {
                "job_id": job.job_id,
                "ingest_status": "INGESTED",
                "dedupe": False
            }
            
        except Exception as e:
            logger.error(f"Job ingestion failed: {e}")
            db.rollback()
            return {
                "job_id": None,
                "ingest_status": "FAILED",
                "error": str(e)
            }
    
    def ingest_batch(
        self,
        jobs: List[Dict[str, Any]],
        source: str,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Ingest multiple jobs.
        
        Args:
            jobs: List of job dictionaries
            source: Source type
            db: Database session
        
        Returns:
            Summary of ingestion results
        """
        if db is None:
            db = next(get_db())
        
        results = {
            "total": len(jobs),
            "ingested": 0,
            "duplicates": 0,
            "failed": 0,
            "job_ids": []
        }
        
        for job_data in jobs:
            result = self.ingest_job(
                source=source,
                source_url=job_data.get("url", ""),
                title=job_data.get("title", ""),
                company=job_data.get("company", ""),
                location=job_data.get("location", ""),
                description=job_data.get("description", ""),
                html_content=job_data.get("html_content"),
                posted_at=job_data.get("posted_at"),
                db=db
            )
            
            if result["ingest_status"] == "INGESTED":
                results["ingested"] += 1
                results["job_ids"].append(result["job_id"])
            elif result["ingest_status"] == "DUPLICATE":
                results["duplicates"] += 1
            else:
                results["failed"] += 1
        
        logger.info(
            f"Batch ingestion completed: {results['ingested']} ingested, "
            f"{results['duplicates']} duplicates, {results['failed']} failed"
        )
        
        return results
