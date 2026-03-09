"""Outcome tracking — user_id from auth, feedback loop per user."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional, Dict, Any
from pydantic import BaseModel

from packages.database.connection import get_db
from packages.database.models import Application, Outcome, JobScore
from apps.web.auth import get_current_user
from packages.common.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/applications", tags=["outcomes"])

STAGE_SIGNAL: Dict[str, int] = {
    "rejected": -1,
    "no_response": 0,
    "phone_screen": +1,
    "onsite": +2,
    "offer": +3,
}


class OutcomeCreate(BaseModel):
    stage: str
    source: str = "manual"
    details: Optional[Dict[str, Any]] = None


@router.post("/{application_id}/outcome")
async def record_outcome(
    application_id: UUID,
    body: OutcomeCreate,
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record outcome for an application owned by the current user."""
    valid_stages = list(STAGE_SIGNAL.keys())
    if body.stage not in valid_stages:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {valid_stages}")

    # Ownership check — application must belong to current user
    application = (
        db.query(Application)
        .filter(
            Application.application_id == application_id,
            Application.user_id == current_user_id,
        )
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found or not yours.")

    outcome = Outcome(
        application_id=application_id,
        stage=body.stage,
        source=body.source,
        details=body.details or {},
    )
    db.add(outcome)

    # Feedback loop: annotate the user's job score with outcome signal
    job_score = (
        db.query(JobScore)
        .filter(
            JobScore.job_id == application.job_id,
            JobScore.user_id == current_user_id,  # only this user's score
        )
        .first()
    )

    feedback_summary = None
    if job_score:
        signal = STAGE_SIGNAL[body.stage]
        note = f" | Outcome: {body.stage} (signal={signal:+d})"
        if note not in (job_score.rationale or ""):
            job_score.rationale = (job_score.rationale or "") + note

        breakdown = dict(job_score.breakdown or {})
        breakdown["_outcome_feedback"] = {
            "stage": body.stage,
            "signal": signal,
            "score_at_time": job_score.total_score,
            "verdict_at_time": job_score.verdict,
        }
        job_score.breakdown = breakdown

        feedback_summary = {
            "job_id": str(application.job_id),
            "score_at_time": job_score.total_score,
            "outcome_signal": signal,
            "interpretation": _interpret(signal, job_score.total_score),
        }

    db.commit()
    return {
        "outcome_id": str(outcome.outcome_id),
        "application_id": str(application_id),
        "stage": body.stage,
        "feedback_loop": feedback_summary,
    }


@router.get("/{application_id}/outcomes")
async def get_outcomes(
    application_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get outcomes for an application — ownership enforced."""
    application = (
        db.query(Application)
        .filter(
            Application.application_id == application_id,
            Application.user_id == current_user_id,
        )
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found or not yours.")

    outcomes = (
        db.query(Outcome)
        .filter(Outcome.application_id == application_id)
        .order_by(Outcome.updated_at.desc())
        .all()
    )
    return [{"outcome_id": str(o.outcome_id), "stage": o.stage, "source": o.source, "details": o.details, "updated_at": o.updated_at.isoformat()} for o in outcomes]


@router.get("/")
async def list_applications(
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all applications for the authenticated user only."""
    apps = (
        db.query(Application)
        .filter(Application.user_id == current_user_id)
        .order_by(Application.created_at.desc())
        .all()
    )
    return [
        {
            "application_id": str(a.application_id),
            "job_id": str(a.job_id),
            "apply_mode": a.apply_mode,
            "status": a.status,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            "created_at": a.created_at.isoformat(),
        }
        for a in apps
    ]


@router.get("/feedback/summary")
async def get_feedback_summary(
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Score calibration summary — only the current user's data."""
    scores = (
        db.query(JobScore)
        .filter(JobScore.user_id == current_user_id)
        .all()
    )
    scores_with_feedback = [
        s for s in scores
        if isinstance(s.breakdown, dict) and "_outcome_feedback" in s.breakdown
    ]

    if not scores_with_feedback:
        return {"message": "No outcome feedback yet.", "total_with_feedback": 0}

    bands: Dict[str, list] = {"50-64": [], "65-74": [], "75-84": [], "85-100": []}
    for s in scores_with_feedback:
        fb = s.breakdown["_outcome_feedback"]
        sc = s.total_score
        band = "85-100" if sc >= 85 else "75-84" if sc >= 75 else "65-74" if sc >= 65 else "50-64"
        bands[band].append({"score": sc, "outcome": fb.get("stage"), "signal": fb.get("signal")})

    summary = {}
    for band, items in bands.items():
        if items:
            positive = sum(1 for i in items if i["signal"] > 0)
            summary[band] = {
                "count": len(items),
                "callback_rate": f"{positive / len(items) * 100:.0f}%",
                "avg_signal": round(sum(i["signal"] for i in items) / len(items), 2),
            }

    return {"total_with_feedback": len(scores_with_feedback), "score_band_performance": summary}


def _interpret(signal: int, score: int) -> str:
    if signal > 0 and score >= 75:
        return "Score calibrated correctly."
    elif signal > 0 and score < 75:
        return "Score underestimated fit."
    elif signal < 0 and score >= 85:
        return "Score overestimated fit — review scoring weights."
    else:
        return "Neutral signal."
