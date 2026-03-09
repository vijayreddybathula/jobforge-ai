"""Job ingestion API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from uuid import UUID

from packages.database.connection import get_db
from packages.database.models import JobRaw, JobParsed
from services.job_ingestion.ingestion_service import IngestionService
from services.job_ingestion.sources.jsearch_source import JSearchSource
from services.jd_parser.jd_parser import JDParser
from services.jd_parser.fallback_parser import FallbackParser
from packages.common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

ingestion_service = IngestionService()
jd_parser = JDParser()
fallback_parser = FallbackParser()


@router.post("/search", summary="Search and ingest jobs via JSearch API")
async def search_and_ingest_jobs(
    keywords: str = Query(..., description="Role keywords e.g. 'Senior GenAI Engineer'"),
    location: str = Query("United States", description="Location e.g. 'Dallas, TX'"),
    work_type: Optional[str] = Query(None, description="remote, hybrid, onsite (comma-separated)"),
    date_posted: Optional[str] = Query(None, description="today, 3days, week, month"),
    max_results: int = Query(20, ge=1, le=50, description="Max jobs to fetch"),
    auto_parse: bool = Query(True, description="Auto-trigger JD parsing after ingestion"),
    db: Session = Depends(get_db),
):
    """
    Search LinkedIn/Indeed jobs via JSearch API, ingest into Postgres,
    and optionally auto-parse each job description with LLM.

    This is the primary job ingestion endpoint — container native,
    no external dependencies beyond JSEARCH_API_KEY in .env.
    """
    try:
        jsearch = JSearchSource()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 1. Fetch jobs from JSearch API
    logger.info(f"Searching jobs: '{keywords}' in '{location}'")
    raw_jobs = jsearch.search_jobs(
        keywords=keywords,
        location=location,
        work_type=work_type,
        date_posted=date_posted,
        max_results=max_results,
    )

    if not raw_jobs:
        return {
            "message": "No jobs found from JSearch API",
            "keywords": keywords,
            "location": location,
            "ingested": 0,
            "duplicates": 0,
            "failed": 0,
            "job_ids": [],
        }

    # 2. Ingest into Postgres (with dedup)
    ingest_result = ingestion_service.ingest_batch(
        jobs=raw_jobs, source="jsearch", db=db
    )

    ingested_job_ids = ingest_result.get("job_ids", [])

    # 3. Auto-parse each newly ingested job
    parse_results = {"parsed": 0, "failed": 0}
    if auto_parse and ingested_job_ids:
        for job_id in ingested_job_ids:
            try:
                job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
                if not job or not job.text_content:
                    continue

                # Skip if already parsed
                existing = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
                if existing:
                    continue

                try:
                    parsed_jd = jd_parser.parse(job.text_content)
                    parser_version = "jd-parser-v1"
                except Exception:
                    parsed_jd = fallback_parser.parse(job.text_content)
                    parser_version = "fallback-parser-v1"

                job_parsed = JobParsed(
                    job_id=job_id,
                    parsed_json=parsed_jd.dict(),
                    parser_version=parser_version,
                    parse_status="PARSED",
                )
                db.add(job_parsed)
                db.commit()
                parse_results["parsed"] += 1

            except Exception as e:
                logger.error(f"Auto-parse failed for job {job_id}: {e}")
                parse_results["failed"] += 1

    return {
        "message": "Job search and ingestion complete",
        "keywords": keywords,
        "location": location,
        "total_fetched": len(raw_jobs),
        "ingested": ingest_result.get("ingested", 0),
        "duplicates": ingest_result.get("duplicates", 0),
        "failed": ingest_result.get("failed", 0),
        "parsed": parse_results["parsed"],
        "job_ids": ingested_job_ids,
    }


@router.post("/ingest", summary="Manually ingest a single job")
async def ingest_job(
    source: str,
    source_url: str,
    title: str,
    company: str,
    location: str,
    description: str,
    db: Session = Depends(get_db),
):
    """Manually ingest a single job posting."""
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


@router.post("/ingest/batch", summary="Manually ingest a batch of jobs")
async def ingest_batch(
    jobs: List[Dict[str, Any]],
    source: str,
    db: Session = Depends(get_db),
):
    """Manually ingest multiple job postings."""
    result = ingestion_service.ingest_batch(jobs=jobs, source=source, db=db)
    return result


@router.post("/{job_id}/parse", summary="Parse a job description with LLM")
async def parse_job(job_id: UUID, db: Session = Depends(get_db)):
    """Parse a job description using LLM (with fallback)."""
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    existing = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    if existing:
        return {
            "job_id": job_id,
            "parse_status": existing.parse_status,
            "parsed_jd": existing.parsed_json,
        }

    try:
        try:
            parsed_jd = jd_parser.parse(job.text_content)
            parser_version = "jd-parser-v1"
        except Exception:
            parsed_jd = fallback_parser.parse(job.text_content)
            parser_version = "fallback-parser-v1"

        job_parsed = JobParsed(
            job_id=job_id,
            parsed_json=parsed_jd.dict(),
            parser_version=parser_version,
            parse_status="PARSED",
        )
        db.add(job_parsed)
        db.commit()

        logger.info(f"Job parsed: {job_id}")
        return {"job_id": job_id, "parse_status": "PARSED", "parsed_jd": parsed_jd.dict()}

    except Exception as e:
        logger.error(f"JD parsing failed for {job_id}: {e}")

        job_parsed = JobParsed(
            job_id=job_id, parsed_json={}, parser_version="none", parse_status="PARSE_FAILED"
        )
        db.add(job_parsed)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse job: {str(e)}",
        )


@router.get("/{job_id}/parsed", summary="Get parsed job description")
async def get_parsed_job(job_id: UUID, db: Session = Depends(get_db)):
    """Get parsed job description."""
    parsed = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parsed job not found. Call POST /{job_id}/parse first.",
        )
    return {
        "job_id": job_id,
        "parse_status": parsed.parse_status,
        "parsed_jd": parsed.parsed_json,
        "parser_version": parsed.parser_version,
    }


@router.get("/ingest/status/{job_id}", summary="Get ingestion status")
async def get_ingest_status(job_id: UUID, db: Session = Depends(get_db)):
    """Get ingestion status for a job."""
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return {
        "job_id": job.job_id,
        "ingest_status": job.ingest_status,
        "source": job.source,
        "title": job.title,
        "company": job.company,
        "created_at": job.created_at.isoformat(),
    }
