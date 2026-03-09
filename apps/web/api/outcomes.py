"""Outcome tracking API endpoints — wired to feedback loop."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from packages.database.connection import get_db
from packages.database.models import Application, Outcome, JobScore
from packages.common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/applications", tags=["outcomes"])

# Stage progression order for feedback scoring
STAGE_SIGNAL: Dict[str, int] = {
    "rejected": -1,       # Negative signal — score was too high
    "no_response": 0,     # Neutral
    "phone_screen": +1,   # Positive signal
    "onsite": +2,         # Strong positive
    "offer": +3,          # Very strong positive
}


class OutcomeCreate(BaseModel):
    stage: str  # rejected, phone_screen, onsite, offer, no_response
    source: str = "manual"  # manual, email
    details: Optional[Dict[str, Any]] = None


@router.post("/{application_id}/outcome")
async def record_outcome(
    application_id: UUID,
    body: OutcomeCreate,
    db: Session = Depends(get_db),
):
    """
    Record application outcome and feed signal back to scoring.
    This closes the feedback loop: outcomes improve future score calibration.

    Stages: rejected | no_response | phone_screen | onsite | offer
    """
    valid_stages = list(STAGE_SIGNAL.keys())
    if body.stage not in valid_stages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stage. Must be one of: {valid_stages}",
        )

    application = db.query(Application).filter(
        Application.application_id == application_id
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Record outcome
    outcome = Outcome(
        application_id=application_id,
        stage=body.stage,
        source=body.source,
        details=body.details or {},
    )
    db.add(outcome)

    # --- Feedback loop: annotate the job score with outcome signal ---
    job_score = db.query(JobScore).filter(
        JobScore.job_id == application.job_id,
        JobScore.user_id == application.user_id,
    ).first()

    feedback_summary = None
    if job_score:
        signal = STAGE_SIGNAL[body.stage]
        existing_details = body.details or {}

        # Store outcome signal in score rationale for future analysis
        feedback_note = f" | Outcome: {body.stage} (signal={signal:+d})"
        if feedback_note not in (job_score.rationale or ""):
            job_score.rationale = (job_score.rationale or "") + feedback_note

        # Store structured feedback in breakdown for analytics
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
            "verdict_at_time": job_score.verdict,
            "outcome_signal": signal,
            "interpretation": _interpret_signal(signal, job_score.total_score),
        }

        logger.info(
            f"Feedback loop: job={application.job_id} score={job_score.total_score} "
            f"verdict={job_score.verdict} outcome={body.stage} signal={signal:+d}"
        )

    db.commit()

    return {
        "outcome_id": str(outcome.outcome_id),
        "application_id": str(application_id),
        "stage": body.stage,
        "source": body.source,
        "created_at": outcome.updated_at.isoformat(),
        "feedback_loop": feedback_summary,
    }


@router.get("/{application_id}/outcomes")
async def get_outcomes(application_id: UUID, db: Session = Depends(get_db)):
    """Get all outcomes for an application."""
    outcomes = db.query(Outcome).filter(
        Outcome.application_id == application_id
    ).order_by(Outcome.updated_at.desc()).all()

    return [
        {
            "outcome_id": str(o.outcome_id),
            "stage": o.stage,
            "source": o.source,
            "details": o.details,
            "updated_at": o.updated_at.isoformat(),
        }
        for o in outcomes
    ]


@router.get("/feedback/summary")
async def get_feedback_summary(db: Session = Depends(get_db)):
    """
    Aggregate outcome signals across all scored jobs.
    Shows calibration data: are high-scoring jobs actually getting callbacks?
    """
    scores_with_outcomes = db.query(JobScore).filter(
        JobScore.breakdown.op('->>')('_outcome_feedback') != None  # noqa
    ).all()

    if not scores_with_outcomes:
        return {
            "message": "No outcome feedback recorded yet. Submit applications and record outcomes to see calibration data.",
            "total_with_feedback": 0,
        }

    bands = {"50-64": [], "65-74": [], "75-84": [], "85-100": []}
    for score in scores_with_outcomes:
        feedback = (score.breakdown or {}).get("_outcome_feedback", {})
        s = score.total_score
        band = "85-100" if s >= 85 else "75-84" if s >= 75 else "65-74" if s >= 65 else "50-64"
        bands[band].append({
            "score": s,
            "verdict": score.verdict,
            "outcome": feedback.get("stage"),
            "signal": feedback.get("signal"),
        })

    summary = {}
    for band, items in bands.items():
        if items:
            avg_signal = sum(i["signal"] for i in items) / len(items)
            positive = sum(1 for i in items if i["signal"] > 0)
            summary[band] = {
                "count": len(items),
                "callback_rate": f"{positive / len(items) * 100:.0f}%",
                "avg_signal": round(avg_signal, 2),
                "outcomes": [i["outcome"] for i in items],
            }

    return {
        "total_with_feedback": len(scores_with_outcomes),
        "score_band_performance": summary,
        "insight": _generate_insight(summary),
    }


def _interpret_signal(signal: int, score: int) -> str:
    if signal > 0 and score >= 75:
        return "Score calibrated correctly — positive outcome for high-scoring job."
    elif signal > 0 and score < 75:
        return "Score underestimated fit — consider lowering verdict thresholds."
    elif signal < 0 and score >= 85:
        return "Score overestimated fit — high scorer got rejected. Review scoring weights."
    elif signal < 0 and score < 65:
        return "Expected rejection for low-scoring job — scoring working correctly."
    else:
        return "Neutral signal — insufficient data to draw conclusions."


def _generate_insight(summary: Dict) -> str:
    high_band = summary.get("85-100", {})
    if high_band and high_band.get("count", 0) >= 3:
        rate = int(high_band["callback_rate"].replace("%", ""))
        if rate >= 60:
            return "Scoring well-calibrated: 85+ score jobs converting at high callback rate."
        elif rate < 30:
            return "WARNING: 85+ score jobs underperforming. Review scoring weights — may be overscoring."
    return "Insufficient data for calibration insight. Keep recording outcomes."
