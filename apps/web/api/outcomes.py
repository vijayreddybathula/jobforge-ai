"""Outcome tracking API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional, Dict, Any

from packages.database.connection import get_db
from packages.database.models import Application, Outcome
from packages.common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/applications", tags=["outcomes"])


@router.post("/{application_id}/outcome")
async def record_outcome(
    application_id: UUID,
    stage: str,  # rejected, phone_screen, onsite, offer
    source: str = "manual",  # manual, email
    details: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db)
):
    """Record application outcome."""
    # Validate stage
    valid_stages = ["rejected", "phone_screen", "onsite", "offer"]
    if stage not in valid_stages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage. Must be one of: {valid_stages}"
        )
    
    # Get application
    application = db.query(Application).filter(
        Application.application_id == application_id
    ).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Create outcome record
    outcome = Outcome(
        application_id=application_id,
        stage=stage,
        source=source,
        details=details or {}
    )
    
    db.add(outcome)
    db.commit()
    
    logger.info(f"Outcome recorded: {application_id} -> {stage}")
    
    return {
        "outcome_id": outcome.outcome_id,
        "application_id": application_id,
        "stage": stage,
        "source": source,
        "created_at": outcome.updated_at.isoformat()
    }


@router.get("/{application_id}/outcomes")
async def get_outcomes(
    application_id: UUID,
    db: Session = Depends(get_db)
):
    """Get all outcomes for application."""
    outcomes = db.query(Outcome).filter(
        Outcome.application_id == application_id
    ).order_by(Outcome.updated_at.desc()).all()
    
    return [
        {
            "outcome_id": str(o.outcome_id),
            "stage": o.stage,
            "source": o.source,
            "details": o.details,
            "updated_at": o.updated_at.isoformat()
        }
        for o in outcomes
    ]
