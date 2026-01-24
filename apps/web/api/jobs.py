"""Job ingestion API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from uuid import UUID

from packages.database.connection import get_db
from packages.database.models import JobRaw, JobParsed, IngestionSource
from services.job_ingestion.ingestion_service import IngestionService
from services.job_ingestion.sources.linkedin_scraper import LinkedInScraper
from services.jd_parser.jd_parser import JDParser
from services.jd_parser.fallback_parser import FallbackParser
from packages.common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

ingestion_service = IngestionService()
linkedin_scraper = LinkedInScraper()
jd_parser = JDParser()
fallback_parser = FallbackParser()


@router.post("/ingest")
async def ingest_job(
    source: str,
    source_url: str,
    title: str,
    company: str,
    location: str,
    description: str,
    db: Session = Depends(get_db)
):
    """Ingest a single job posting."""
    result = ingestion_service.ingest_job(
        source=source,
        source_url=source_url,
        title=title,
        company=company,
        location=location,
        description=description,
        db=db
    )
    
    return result


@router.post("/ingest/batch")
async def ingest_batch(
    jobs: List[Dict[str, Any]],
    source: str,
    db: Session = Depends(get_db)
):
    """Ingest multiple jobs."""
    result = ingestion_service.ingest_batch(
        jobs=jobs,
        source=source,
        db=db
    )
    
    return result


@router.post("/ingest/linkedin")
async def ingest_from_linkedin(
    search_url: str,
    max_jobs: int = 10,
    db: Session = Depends(get_db)
):
    """Scrape and ingest jobs from LinkedIn."""
    try:
        # Scrape jobs
        jobs = linkedin_scraper.scrape_search_results(search_url, max_jobs)
        
        if not jobs:
            return {
                "message": "No jobs found",
                "ingested": 0
            }
        
        # Ingest jobs
        result = ingestion_service.ingest_batch(
            jobs=jobs,
            source="linkedin",
            db=db
        )
        
        return result
        
    except Exception as e:
        logger.error(f"LinkedIn ingestion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest from LinkedIn: {str(e)}"
        )


@router.post("/{job_id}/parse")
async def parse_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    """Parse a job description."""
    # Get job
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Check if already parsed
    existing = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    if existing:
        return {
            "job_id": job_id,
            "parse_status": existing.parse_status,
            "parsed_jd": existing.parsed_json
        }
    
    try:
        # Parse with LLM (with caching)
        parsed_jd = jd_parser.parse(job.text_content)
        
        # Save to database
        job_parsed = JobParsed(
            job_id=job_id,
            parsed_json=parsed_jd.dict(),
            parser_version="jd-parser-v1",
            parse_status="PARSED"
        )
        
        db.add(job_parsed)
        db.commit()
        
        logger.info(f"Job parsed: {job_id}")
        
        return {
            "job_id": job_id,
            "parse_status": "PARSED",
            "parsed_jd": parsed_jd.dict()
        }
        
    except Exception as e:
        logger.error(f"JD parsing failed for {job_id}: {e}")
        
        # Try fallback parser
        try:
            parsed_jd = fallback_parser.parse(job.text_content)
            
            job_parsed = JobParsed(
                job_id=job_id,
                parsed_json=parsed_jd.dict(),
                parser_version="fallback-parser-v1",
                parse_status="PARSED"
            )
            
            db.add(job_parsed)
            db.commit()
            
            logger.info(f"Job parsed with fallback: {job_id}")
            
            return {
                "job_id": job_id,
                "parse_status": "PARSED",
                "parsed_jd": parsed_jd.dict()
            }
        except Exception as fallback_error:
            logger.error(f"Fallback parsing also failed: {fallback_error}")
            
            # Mark as failed
            job_parsed = JobParsed(
                job_id=job_id,
                parsed_json={},
                parser_version="none",
                parse_status="PARSE_FAILED"
            )
            
            db.add(job_parsed)
            db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse job: {str(e)}"
            )


@router.get("/{job_id}/parsed")
async def get_parsed_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    """Get parsed job description."""
    parsed = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parsed job not found. Call POST /parse first."
        )
    
    return {
        "job_id": job_id,
        "parse_status": parsed.parse_status,
        "parsed_jd": parsed.parsed_json,
        "parser_version": parsed.parser_version
    }


@router.get("/ingest/status/{job_id}")
async def get_ingest_status(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    """Get ingestion status for a job."""
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return {
        "job_id": job.job_id,
        "ingest_status": job.ingest_status,
        "source": job.source,
        "created_at": job.created_at.isoformat()
    }
