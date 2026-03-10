"""Job ingestion service."""

from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from packages.database.models import JobRaw, IngestionSource, ScrapingSession
from packages.database.connection import get_db
from packages.common.rate_limiter import RateLimiter
from packages.common.redis_cache import get_redis_cache
from packages.common.logging import get_logger
from services.job_ingestion.normalizer import JobNormalizer

logger = get_logger(__name__)

# How old a job must be (in days) before we allow re-ingesting a title+company
# match as a genuinely new posting.  Prevents duplicates from re-searches but
# lets the same role be re-posted weeks later as a real new listing.
_SOFT_DEDUP_WINDOW_DAYS = 14


class IngestionService:
    """Service for ingesting jobs from various sources."""

    def __init__(self):
        self.normalizer   = JobNormalizer()
        self.rate_limiter = RateLimiter()
        self.cache        = get_redis_cache()

    def ingest_job(
        self,
        source: str,
        source_url: str,
        title: str,
        company: str,
        location: str,
        description: str,
        apply_link: Optional[str] = None,
        html_content: Optional[str] = None,
        posted_at: Optional[datetime] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Ingest a single job posting.

        Deduplication strategy (two layers):

        Layer 1 — content_hash (title + company + desc[:1000]):
          Catches exact or near-exact reposts.

        Layer 2 — soft dedup on (title_norm, company_norm, source):
          Catches the same role re-fetched with slightly different description
          wording (JSearch does this across searches).  If a job with the same
          normalised title + company was ingested within _SOFT_DEDUP_WINDOW_DAYS,
          treat it as a duplicate and update apply_link only.

        apply_link:  direct ATS/employer URL shown on the Apply button.
        source_url:  canonical dedup URL (e.g. JSearch’s job_url).
        """
        if db is None:
            db = next(get_db())

        try:
            normalized    = self.normalizer.normalize(
                title=title, company=company, location=location, description=description
            )
            content_hash  = normalized["content_hash"]
            title_norm    = normalized["title"]
            company_norm  = normalized["company"]

            # ── Layer 1: exact content-hash dedup ──────────────────────────────
            seen_key = f"jobs:seen:{content_hash}"
            if self.cache.is_in_set(seen_key, content_hash):
                logger.debug(f"Job already seen (cache): {content_hash[:8]}")
                return {"job_id": None, "ingest_status": "DUPLICATE", "dedupe": True}

            existing_hash = db.query(JobRaw).filter(JobRaw.content_hash == content_hash).first()
            if existing_hash:
                if apply_link and not existing_hash.apply_link:
                    existing_hash.apply_link = apply_link
                    db.commit()
                self.cache.add_to_set(seen_key, content_hash)
                return {"job_id": existing_hash.job_id, "ingest_status": "DUPLICATE", "dedupe": True}

            # ── Layer 2: soft dedup on title + company + source within window ───
            # JSearch returns the same role with slightly different descriptions
            # on repeated searches, producing a new content_hash each time.
            # If title_norm + company_norm + source already exist and the job
            # was ingested within the last 14 days, treat it as a duplicate.
            window_cutoff = datetime.utcnow() - timedelta(days=_SOFT_DEDUP_WINDOW_DAYS)
            existing_soft = (
                db.query(JobRaw)
                .filter(
                    JobRaw.title   == title_norm,
                    JobRaw.company == company_norm,
                    JobRaw.source  == source,
                    JobRaw.created_at >= window_cutoff,
                )
                .first()
            )
            if existing_soft:
                # Update apply_link if we have a fresher one
                if apply_link and not existing_soft.apply_link:
                    existing_soft.apply_link = apply_link
                    db.commit()
                logger.debug(
                    f"Soft-dedup hit: '{title_norm}' @ '{company_norm}' already ingested "
                    f"within {_SOFT_DEDUP_WINDOW_DAYS}d (id={existing_soft.job_id})"
                )
                return {"job_id": existing_soft.job_id, "ingest_status": "DUPLICATE", "dedupe": True}

            # ── New job ──────────────────────────────────────────────────────────────
            job = JobRaw(
                source=source,
                source_url=source_url,
                apply_link=apply_link or source_url,
                company=company_norm,
                title=title_norm,
                location=normalized["location"],
                text_content=normalized["description"],
                content_hash=content_hash,
                posted_at=posted_at,
                ingest_status="INGESTED",
            )

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
            self.cache.add_to_set(seen_key, content_hash)
            logger.info(f"Job ingested: {job.job_id} '{title_norm}' @ '{company_norm}' from {source}")
            return {"job_id": job.job_id, "ingest_status": "INGESTED", "dedupe": False}

        except Exception as e:
            logger.error(f"Job ingestion failed: {e}")
            db.rollback()
            return {"job_id": None, "ingest_status": "FAILED", "error": str(e)}

    def ingest_batch(
        self, jobs: List[Dict[str, Any]], source: str, db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Ingest multiple jobs."""
        if db is None:
            db = next(get_db())

        results = {"total": len(jobs), "ingested": 0, "duplicates": 0, "failed": 0, "job_ids": []}

        for job_data in jobs:
            result = self.ingest_job(
                source=source,
                source_url=job_data.get("url", ""),
                apply_link=job_data.get("apply_link"),
                title=job_data.get("title", ""),
                company=job_data.get("company", ""),
                location=job_data.get("location", ""),
                description=job_data.get("description", ""),
                html_content=job_data.get("html_content"),
                posted_at=job_data.get("posted_at"),
                db=db,
            )
            if result["ingest_status"] == "INGESTED":
                results["ingested"] += 1
                results["job_ids"].append(result["job_id"])
            elif result["ingest_status"] == "DUPLICATE":
                results["duplicates"] += 1
            else:
                results["failed"] += 1

        logger.info(
            f"Batch ingestion: {results['ingested']} ingested, "
            f"{results['duplicates']} duplicates, {results['failed']} failed"
        )
        return results
