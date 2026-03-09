"""Scoring API endpoints — user_id from auth, not query params."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from packages.database.connection import get_db
from packages.database.models import JobRaw, JobParsed, UserProfile, UserPreferences, JobScore
from services.scoring.rules_engine import RulesEngine
from services.scoring.scoring_service import ScoringService
from apps.web.auth import get_current_user
from packages.common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["scoring"])

rules_engine    = RulesEngine()
scoring_service = ScoringService()


def _get_user_context(current_user_id: UUID, db: Session):
    """Load and validate user profile + preferences. Raises 4xx with clear messages."""
    user_profile = db.query(UserProfile).filter(UserProfile.user_id == current_user_id).first()
    if not user_profile:
        raise HTTPException(
            status_code=404,
            detail=(
                "No profile found for your account. "
                "Please upload a resume, run Analyze, confirm your roles, "
                "then hit POST /profile/build-from-resume/{resume_id}."
            ),
        )
    user_preferences = db.query(UserPreferences).filter(UserPreferences.user_id == current_user_id).first()
    if not user_preferences:
        raise HTTPException(
            status_code=404,
            detail="Job preferences not set. Go to the Preferences page and save your settings first.",
        )
    return user_profile, user_preferences


@router.post("/{job_id}/score")
async def score_job(
    job_id: UUID,
    force_reparse: bool = Query(False, description="Auto-parse the job first if not yet parsed"),
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Score a job for the authenticated user.
    If the job is not yet parsed, automatically parses it first (unless it has no text content).
    """
    from services.jd_parser.jd_parser import JDParser
    from services.jd_parser.fallback_parser import FallbackParser
    from packages.schemas.jd_schema import ParsedJD

    job = db.query(JobRaw).filter(JobRaw.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    parsed = db.query(JobParsed).filter(JobParsed.job_id == job_id).first()

    # Auto-parse if needed instead of refusing with a hard error
    if not parsed or parsed.parse_status != "PARSED" or force_reparse:
        if not job.text_content:
            raise HTTPException(
                status_code=422,
                detail="This job has no text content and cannot be parsed or scored. It may be a stub entry.",
            )
        logger.info(f"Auto-parsing job {job_id} before scoring")
        if parsed:
            db.delete(parsed); db.commit()
        try:
            jd_parser   = JDParser()
            parsed_data = jd_parser.parse(job.text_content)
            ver         = "jd-parser-v1"
        except Exception:
            fallback    = FallbackParser()
            parsed_data = fallback.parse(job.text_content)
            ver         = "fallback-parser-v1"
        parsed = JobParsed(job_id=job_id, parsed_json=parsed_data.dict(),
                           parser_version=ver, parse_status="PARSED")
        db.add(parsed); db.commit(); db.refresh(parsed)

    user_profile, user_preferences = _get_user_context(current_user_id, db)

    parsed_jd = ParsedJD(**parsed.parsed_json)

    is_allowed, rejection_reason = rules_engine.check_constraints(parsed_jd, user_preferences)
    if not is_allowed:
        return {
            "job_id":      str(job_id),
            "user_id":     str(current_user_id),
            "total_score": 0,
            "verdict":     "REJECTED",
            "rationale":   rejection_reason,
        }

    return scoring_service.score_job(
        job_id=job_id,
        user_id=current_user_id,
        parsed_jd=parsed_jd,
        user_profile=user_profile,
        user_preferences=user_preferences,
        db=db,
    )


@router.get("/{job_id}/score")
async def get_score(
    job_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    score = (
        db.query(JobScore)
        .filter(JobScore.job_id == job_id, JobScore.user_id == current_user_id)
        .first()
    )
    if not score:
        raise HTTPException(status_code=404, detail="Score not found. Call POST /jobs/{id}/score first.")
    return {
        "job_id":      str(score.job_id),
        "user_id":     str(score.user_id),
        "total_score": score.total_score,
        "breakdown":   score.breakdown,
        "verdict":     score.verdict,
        "rationale":   score.rationale,
        "created_at":  score.created_at.isoformat(),
    }


@router.post("/score-all")
async def score_all_jobs(
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Score ALL jobs (parsed or not) for the authenticated user.
    Jobs not yet parsed are auto-parsed first.
    Jobs with no text content are skipped with a count.
    """
    from services.jd_parser.jd_parser import JDParser
    from services.jd_parser.fallback_parser import FallbackParser
    from packages.schemas.jd_schema import ParsedJD

    user_profile, user_preferences = _get_user_context(current_user_id, db)

    all_jobs = db.query(JobRaw).all()

    already_scored = {
        str(s.job_id)
        for s in db.query(JobScore).filter(JobScore.user_id == current_user_id).all()
    }
    parsed_map = {
        str(p.job_id): p
        for p in db.query(JobParsed).filter(JobParsed.parse_status == "PARSED").all()
    }

    jd_parser_inst = JDParser()
    fallback_inst  = FallbackParser()

    results = {"scored": 0, "skipped_already_scored": 0,
               "skipped_no_content": 0, "auto_parsed": 0, "failed": 0, "rejected": 0}

    for job in all_jobs:
        jid = str(job.job_id)

        if jid in already_scored:
            results["skipped_already_scored"] += 1
            continue

        # Auto-parse if needed
        parsed = parsed_map.get(jid)
        if not parsed:
            if not job.text_content:
                results["skipped_no_content"] += 1
                continue
            try:
                try:
                    pd  = jd_parser_inst.parse(job.text_content)
                    ver = "jd-parser-v1"
                except Exception:
                    pd  = fallback_inst.parse(job.text_content)
                    ver = "fallback-parser-v1"
                new_parsed = JobParsed(job_id=job.job_id, parsed_json=pd.dict(),
                                       parser_version=ver, parse_status="PARSED")
                db.add(new_parsed); db.commit(); db.refresh(new_parsed)
                parsed_map[jid] = new_parsed
                parsed = new_parsed
                results["auto_parsed"] += 1
            except Exception as e:
                logger.error(f"score-all auto-parse failed for {job.job_id}: {e}")
                results["failed"] += 1
                continue

        try:
            parsed_jd = ParsedJD(**parsed.parsed_json)
            is_allowed, reason = rules_engine.check_constraints(parsed_jd, user_preferences)
            if not is_allowed:
                results["rejected"] += 1
                continue
            scoring_service.score_job(
                job_id=job.job_id, user_id=current_user_id,
                parsed_jd=parsed_jd, user_profile=user_profile,
                user_preferences=user_preferences, db=db,
            )
            results["scored"] += 1
        except Exception as e:
            logger.error(f"score-all scoring failed for {job.job_id}: {e}")
            results["failed"] += 1

    return {"message": "Batch scoring complete", "user_id": str(current_user_id), **results}
