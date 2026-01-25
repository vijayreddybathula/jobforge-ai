"""Decision engine API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from packages.database.connection import get_db
from packages.database.models import JobScore
from services.decision_engine.decision_service import DecisionService
from packages.common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["decision"])

decision_service = DecisionService()


@router.get("/{job_id}/decision")
async def get_decision(
    job_id: UUID, user_id: UUID, db: Session = Depends(get_db)  # TODO: Get from authenticated user
):
    """Get decision for job."""
    # Get score
    score = (
        db.query(JobScore).filter(JobScore.job_id == job_id, JobScore.user_id == user_id).first()
    )

    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Score not found. Call POST /score first."
        )

    # Make decision
    decision = decision_service.make_decision(
        job_id=job_id, user_id=user_id, score=score.total_score, verdict=score.verdict, db=db
    )

    return decision


@router.post("/{job_id}/decision/override")
async def override_decision(
    job_id: UUID,
    user_id: UUID,  # TODO: Get from authenticated user
    new_decision: str,
    db: Session = Depends(get_db),
):
    """Manually override decision."""
    # Validate decision
    valid_decisions = ["SKIP", "VALIDATE", "ASSISTED_APPLY", "ELIGIBLE_AUTO_SUBMIT"]
    if new_decision not in valid_decisions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decision. Must be one of: {valid_decisions}",
        )

    # Update score verdict
    score = (
        db.query(JobScore).filter(JobScore.job_id == job_id, JobScore.user_id == user_id).first()
    )

    if not score:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Score not found")

    score.verdict = new_decision
    db.commit()

    logger.info(f"Decision overridden: {job_id} -> {new_decision}")

    return {
        "job_id": job_id,
        "decision": new_decision,
        "message": "Decision overridden successfully",
    }
