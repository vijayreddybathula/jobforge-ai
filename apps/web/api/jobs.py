"""Job ingestion and listing API — listing is user-aware."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from packages.database.connection import get_db
from packages.database.models import JobRaw, JobParsed, JobScore
from services.job_ingestion.ingestion_service import IngestionService
from services.job_ingestion.sources.jsearch_source import JSearchSource
from services.job_ingestion.normalizer import JobNormalizer
from services.jd_parser.jd_parser import JDParser
from services.jd_parser.fallback_parser import FallbackParser
from apps.web.auth import get_current_user
from packages.common.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

ingestion_service = IngestionService()
jd_parser         = JDParser()
fallback_parser   = FallbackParser()
_normalizer       = JobNormalizer()


def _enrich_job(job: JobRaw, parsed: Optional[JobParsed], score: Optional[JobScore]) -> dict:
    """Build the standard job dict enriched with parsed data and user score."""
    return {
        "job_id":       str(job.job_id),
        "title":        job.title,
        "company":      job.company,
        "location":     job.location,
        "source":       job.source,
        "source_url":   str(job.source_url) if job.source_url else None,
        "created_at":   job.created_at.isoformat(),
        "parse_status": parsed.parse_status if parsed else "NOT_PARSED",
        "parsed_role":  parsed.parsed_json.get("role") if parsed and parsed.parsed_json else None,
        "score":        score.total_score if score else None,
        "verdict":      score.verdict     if score else "NOT_SCORED",
        "breakdown":    score.breakdown   if score else None,
        "rationale":    score.rationale   if score else None,
    }


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("/", summary="List all jobs with current user's score status")
async def list_jobs(
    page:        int           = Query(1,  ge=1),
    limit:       int           = Query(20, ge=1, le=100),
    verdict:     Optional[str] = Query(None),
    parsed_only: bool          = Query(False),
    current_user_id: UUID      = Depends(get_current_user),
    db: Session                = Depends(get_db),
):
    query = db.query(JobRaw)
    if parsed_only:
        parsed_ids = {
            p.job_id for p in
            db.query(JobParsed.job_id).filter(JobParsed.parse_status == "PARSED").all()
        }
        query = query.filter(JobRaw.job_id.in_(parsed_ids))

    total = query.count()
    jobs  = query.order_by(JobRaw.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    job_ids    = [j.job_id for j in jobs]
    scores     = {
        str(s.job_id): s for s in
        db.query(JobScore).filter(JobScore.user_id == current_user_id, JobScore.job_id.in_(job_ids)).all()
    }
    parsed_map = {
        str(p.job_id): p for p in
        db.query(JobParsed).filter(JobParsed.job_id.in_(job_ids)).all()
    }

    result = []
    for job in jobs:
        jid  = str(job.job_id)
        item = _enrich_job(job, parsed_map.get(jid), scores.get(jid))
        if verdict and item["verdict"] != verdict:
            continue
        result.append(item)

    return {"jobs": result, "total": total, "page": page, "limit": limit,
            "pages": (total + limit - 1) // limit}


# ── Search & ingest ───────────────────────────────────────────────────────────

@router.post("/search", summary="Search and ingest jobs via JSearch API")
async def search_and_ingest_jobs(
    keywords:      str           = Query(...),
    location:      str           = Query("United States"),
    work_type:     Optional[str] = Query(None),
    date_posted:   Optional[str] = Query(None),
    max_results:   int           = Query(20, ge=1, le=50),
    auto_parse:    bool          = Query(True),
    force_reparse: bool          = Query(False),
    current_user_id: UUID        = Depends(get_current_user),
    db: Session                  = Depends(get_db),
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

    # FIX: collect job_ids for ALL fetched jobs (new + duplicate).
    # Previously only newly-ingested IDs were included, so duplicate jobs
    # were fetched but never parsed or returned — causing the catalog to
    # stay stuck at the initial count even after repeated searches.
    all_candidate_ids = list(ingested_job_ids)  # start with newly ingested
    for job_data in raw_jobs:
        normalized = _normalizer.normalize(
            title=job_data.get("title", ""),
            company=job_data.get("company", ""),
            location=job_data.get("location", ""),
            description=job_data.get("description", ""),
        )
        existing = db.query(JobRaw).filter(
            JobRaw.content_hash == normalized["content_hash"]
        ).first()
        if existing and existing.job_id not in all_candidate_ids:
            all_candidate_ids.append(existing.job_id)

    parse_results = {"parsed": 0, "reparsed": 0, "failed": 0}
    if auto_parse and all_candidate_ids:
        for job_id in all_candidate_ids:
            try:
                job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
                if not job or not job.text_content:
                    continue
                existing_parsed = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
                if existing_parsed and not force_reparse:
                    continue
                if existing_parsed and force_reparse:
                    db.delete(existing_parsed)
                    db.commit()
                try:
                    pjd = jd_parser.parse(job.text_content)
                    ver = "jd-parser-v1"
                except Exception:
                    pjd = fallback_parser.parse(job.text_content)
                    ver = "fallback-parser-v1"
                db.add(JobParsed(
                    job_id=job_id,
                    parsed_json=pjd.dict(),
                    parser_version=ver,
                    parse_status="PARSED",
                ))
                db.commit()
                parse_results["reparsed" if existing_parsed else "parsed"] += 1
            except Exception as e:
                logger.error(f"Auto-parse failed for {job_id}: {e}")
                parse_results["failed"] += 1

    return {
        "message": "Job search and ingestion complete",
        "keywords": keywords,
        "location": location,
        "total_fetched": len(raw_jobs),
        "ingested":   ingest_result.get("ingested", 0),
        "duplicates": ingest_result.get("duplicates", 0),
        "parsed":     parse_results["parsed"],
        "reparsed":   parse_results["reparsed"],
        "job_ids":    [str(jid) for jid in all_candidate_ids],
    }


# ── Bulk parse ────────────────────────────────────────────────────────────────

@router.post("/parse-all", summary="Parse all unparsed jobs in the catalog")
async def parse_all_jobs(
    force_reparse: bool   = Query(False),
    current_user_id: UUID = Depends(get_current_user),
    db: Session           = Depends(get_db),
):
    all_jobs = db.query(JobRaw).all()
    already_parsed = {
        str(p.job_id) for p in
        db.query(JobParsed).filter(JobParsed.parse_status == "PARSED").all()
    }
    results = {"parsed": 0, "skipped": 0, "failed": 0}
    for job in all_jobs:
        jid = str(job.job_id)
        if (jid in already_parsed and not force_reparse) or not job.text_content:
            results["skipped"] += 1
            continue
        try:
            existing = db.query(JobParsed).filter(JobParsed.job_id == job.job_id).first()
            if existing:
                db.delete(existing)
                db.commit()
            try:
                pjd = jd_parser.parse(job.text_content)
                ver = "jd-parser-v1"
            except Exception:
                pjd = fallback_parser.parse(job.text_content)
                ver = "fallback-parser-v1"
            db.add(JobParsed(
                job_id=job.job_id,
                parsed_json=pjd.dict(),
                parser_version=ver,
                parse_status="PARSED",
            ))
            db.commit()
            results["parsed"] += 1
        except Exception as e:
            logger.error(f"parse-all failed for {job.job_id}: {e}")
            results["failed"] += 1
    return {"message": "Bulk parse complete", **results}


# ── Single job parse ──────────────────────────────────────────────────────────

@router.post("/{job_id}/parse")
async def parse_job(
    job_id: UUID,
    force_reparse: bool   = Query(False),
    current_user_id: UUID = Depends(get_current_user),
    db: Session           = Depends(get_db),
):
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    existing = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    if existing and not force_reparse:
        return {"job_id": str(job_id), "parse_status": existing.parse_status, "parsed_jd": existing.parsed_json}
    if existing and force_reparse:
        db.delete(existing)
        db.commit()
    if not job.text_content:
        raise HTTPException(status_code=422, detail="Job has no text content to parse.")
    try:
        try:
            pjd = jd_parser.parse(job.text_content)
            ver = "jd-parser-v1"
        except Exception:
            pjd = fallback_parser.parse(job.text_content)
            ver = "fallback-parser-v1"
        db.add(JobParsed(job_id=job_id, parsed_json=pjd.dict(), parser_version=ver, parse_status="PARSED"))
        db.commit()
        return {"job_id": str(job_id), "parse_status": "PARSED", "parsed_jd": pjd.dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Get parsed JD ─────────────────────────────────────────────────────────────

@router.get("/{job_id}/parsed")
async def get_parsed_job(
    job_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: Session           = Depends(get_db),
):
    parsed = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    if not parsed:
        raise HTTPException(status_code=404, detail="Not parsed yet.")
    return {"job_id": str(job_id), "parse_status": parsed.parse_status,
            "parsed_jd": parsed.parsed_json, "parser_version": parsed.parser_version}


# ── Single job detail — MUST be last so /{job_id}/xxx routes match first ──────

@router.get("/{job_id}", summary="Get a single job enriched with this user's score")
async def get_job(
    job_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: Session           = Depends(get_db),
):
    """
    Direct job lookup by ID. Returns job metadata + this user's score.
    Registered LAST so sub-path routes like /{job_id}/parsed take priority.
    """
    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    parsed = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()
    score  = (
        db.query(JobScore)
        .filter(JobScore.job_id == job_id, JobScore.user_id == current_user_id)
        .first()
    )
    return _enrich_job(job, parsed, score)
