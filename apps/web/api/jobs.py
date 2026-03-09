"""Job ingestion and listing API — listing is user-aware."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from uuid import UUID

from packages.database.connection import get_db
from packages.database.models import JobRaw, JobParsed, JobScore
from services.job_ingestion.ingestion_service import IngestionService
from services.job_ingestion.sources.jsearch_source import JSearchSource
from services.jd_parser.jd_parser import JDParser
from services.jd_parser.fallback_parser import FallbackParser
from apps.web.auth import get_current_user
from packages.common.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

ingestion_service = IngestionService()
jd_parser = JDParser()
fallback_parser = FallbackParser()


@router.get("/", summary="List all jobs with current user's score status")
async def list_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    verdict: Optional[str] = Query(None),
    parsed_only: bool = Query(False),
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(JobRaw)
    if parsed_only:
        parsed_ids = {
            p.job_id
            for p in db.query(JobParsed.job_id)
            .filter(JobParsed.parse_status == "PARSED")
            .all()
        }
        query = query.filter(JobRaw.job_id.in_(parsed_ids))

    total = query.count()
    jobs  = query.order_by(JobRaw.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    job_ids = [j.job_id for j in jobs]
    scores  = {
        str(s.job_id): s
        for s in db.query(JobScore)
        .filter(JobScore.user_id == current_user_id, JobScore.job_id.in_(job_ids))
        .all()
    }
    parsed_map = {
        str(p.job_id): p
        for p in db.query(JobParsed).filter(JobParsed.job_id.in_(job_ids)).all()
    }

    result = []
    for job in jobs:
        jid    = str(job.job_id)
        score  = scores.get(jid)
        parsed = parsed_map.get(jid)

        item = {
            "job_id":       jid,
            "title":        job.title,
            "company":      job.company,
            "location":     job.location,
            "source":       job.source,
            "source_url":   str(job.source_url),
            "created_at":   job.created_at.isoformat(),
            "parse_status": parsed.parse_status if parsed else "NOT_PARSED",
            "parsed_role":  parsed.parsed_json.get("role") if parsed and parsed.parsed_json else None,
            "score":        score.total_score if score else None,
            "verdict":      score.verdict if score else "NOT_SCORED",
            "breakdown":    score.breakdown if score else None,
            "rationale":    score.rationale if score else None,
        }

        if verdict and item["verdict"] != verdict:
            continue
        result.append(item)

    return {"jobs": result, "total": total, "page": page, "limit": limit, "pages": (total + limit - 1) // limit}


@router.post("/search", summary="Search and ingest jobs via JSearch API")
async def search_and_ingest_jobs(
    keywords: str = Query(...),
    location: str = Query("United States"),
    work_type: Optional[str] = Query(None),
    date_posted: Optional[str] = Query(None),
    max_results: int = Query(20, ge=1, le=50),
    auto_parse: bool = Query(True),
    force_reparse: bool = Query(False),
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        jsearch = JSearchSource()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    raw_jobs = jsearch.search_jobs(
        keywords=keywords, location=location,
        work_type=work_type, date_posted=date_posted, max_results=max_results,
    )
    if not raw_jobs:
        return {"message": "No jobs found", "ingested": 0, "duplicates": 0, "job_ids": []}

    ingest_result    = ingestion_service.ingest_batch(jobs=raw_jobs, source="jsearch", db=db)
    ingested_job_ids = ingest_result.get("job_ids", [])

    all_candidate_ids = list(ingested_job_ids)
    if force_reparse and raw_jobs:
        from services.job_ingestion.normalizer import JobNormalizer
        normalizer = JobNormalizer()
        for job_data in raw_jobs:
            normalized = normalizer.normalize(
                title=job_data.get("title", ""), company=job_data.get("company", ""),
                location=job_data.get("location", ""), description=job_data.get("description", ""),
            )
            existing = db.query(JobRaw).filter(JobRaw.content_hash == normalized["content_hash"]).first()
            if existing and existing.job_id not in all_candidate_ids:
                all_candidate_ids.append(existing.job_id)

    parse_results = {"parsed": 0, "reparsed": 0, "failed": 0}
    if auto_parse and all_candidate_ids:
        for job_id in all_candidate_ids:
            try:
                job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
                if not job or not job.text_content:
                    continue
                existing = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
                if existing and not force_reparse:
                    continue
                if existing and force_reparse:
                    db.delete(existing); db.commit()
                try:
                    parsed_jd      = jd_parser.parse(job.text_content)
                    parser_version = "jd-parser-v1"
                except Exception:
                    parsed_jd      = fallback_parser.parse(job.text_content)
                    parser_version = "fallback-parser-v1"
                db.add(JobParsed(job_id=job_id, parsed_json=parsed_jd.dict(),
                                 parser_version=parser_version, parse_status="PARSED"))
                db.commit()
                parse_results["reparsed" if existing else "parsed"] += 1
            except Exception as e:
                logger.error(f"Auto-parse failed for {job_id}: {e}")
                parse_results["failed"] += 1

    return {
        "message": "Job search and ingestion complete",
        "keywords": keywords, "location": location,
        "total_fetched": len(raw_jobs),
        "ingested":   ingest_result.get("ingested", 0),
        "duplicates": ingest_result.get("duplicates", 0),
        "parsed":     parse_results["parsed"],
        "reparsed":   parse_results["reparsed"],
        "job_ids":    ingested_job_ids,
    }


@router.post("/parse-all", summary="Parse all unparse jobs in the catalog")
async def parse_all_jobs(
    force_reparse: bool = Query(False),
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Parse every job in jobs_raw that either has no jobs_parsed row yet,
    or (if force_reparse=true) every job regardless.
    Returns counts of parsed / skipped / failed.
    """
    all_jobs = db.query(JobRaw).all()
    already_parsed = {
        str(p.job_id)
        for p in db.query(JobParsed).filter(JobParsed.parse_status == "PARSED").all()
    }

    results = {"parsed": 0, "skipped": 0, "failed": 0}

    for job in all_jobs:
        jid = str(job.job_id)
        if jid in already_parsed and not force_reparse:
            results["skipped"] += 1
            continue
        if not job.text_content:
            results["skipped"] += 1
            continue
        try:
            existing = db.query(JobParsed).filter(JobParsed.job_id == job.job_id).first()
            if existing:
                db.delete(existing); db.commit()
            try:
                parsed_jd      = jd_parser.parse(job.text_content)
                parser_version = "jd-parser-v1"
            except Exception:
                parsed_jd      = fallback_parser.parse(job.text_content)
                parser_version = "fallback-parser-v1"
            db.add(JobParsed(job_id=job.job_id, parsed_json=parsed_jd.dict(),
                             parser_version=parser_version, parse_status="PARSED"))
            db.commit()
            results["parsed"] += 1
        except Exception as e:
            logger.error(f"parse-all failed for {job.job_id}: {e}")
            results["failed"] += 1

    return {"message": "Bulk parse complete", **results}


@router.post("/{job_id}/parse")
async def parse_job(
    job_id: UUID,
    force_reparse: bool = Query(False),
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    existing = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    if existing and not force_reparse:
        return {"job_id": str(job_id), "parse_status": existing.parse_status, "parsed_jd": existing.parsed_json}
    if existing and force_reparse:
        db.delete(existing); db.commit()

    if not job.text_content:
        raise HTTPException(status_code=422, detail="Job has no text content to parse.")

    try:
        try:
            parsed_jd      = jd_parser.parse(job.text_content)
            parser_version = "jd-parser-v1"
        except Exception:
            parsed_jd      = fallback_parser.parse(job.text_content)
            parser_version = "fallback-parser-v1"
        db.add(JobParsed(job_id=job_id, parsed_json=parsed_jd.dict(),
                         parser_version=parser_version, parse_status="PARSED"))
        db.commit()
        return {"job_id": str(job_id), "parse_status": "PARSED", "parsed_jd": parsed_jd.dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/parsed")
async def get_parsed_job(
    job_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    if not parsed:
        raise HTTPException(status_code=404, detail="Not parsed yet.")
    return {"job_id": str(job_id), "parse_status": parsed.parse_status,
            "parsed_jd": parsed.parsed_json, "parser_version": parsed.parser_version}
