"""Resume API endpoints."""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from packages.database.connection import get_db
from packages.database.models import Resume, RoleMatch as RoleMatchModel, User
from packages.schemas.resume import (
    ResumeUploadResponse,
    ResumeAnalysisResponse,
    RoleConfirmationRequest,
    RoleConfirmationResponse
)
from services.resume_analyzer.resume_parser import ResumeParser
from services.resume_analyzer.role_extractor import RoleExtractor
from packages.common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/resume", tags=["resume"])

# Initialize services
resume_parser = ResumeParser()
role_extractor = RoleExtractor()


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    # user_id: UUID = Depends(get_current_user)  # TODO: Add authentication
):
    """Upload and parse resume."""
    # TODO: Get user_id from authenticated user
    user_id = UUID("00000000-0000-0000-0000-000000000001")  # Placeholder
    
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )
    
    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in ["pdf", "docx", "doc"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}. Supported: pdf, docx, doc"
        )
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Parse resume
        parsed_data = resume_parser.parse_resume(
            file_content=file_content,
            file_name=file.filename,
            user_id=str(user_id)
        )
        
        # Check if resume already exists (by hash)
        existing_resume = db.query(Resume).filter(
            Resume.content_hash == parsed_data["content_hash"]
        ).first()
        
        if existing_resume:
            return ResumeUploadResponse(
                resume_id=existing_resume.resume_id,
                file_name=existing_resume.file_name,
                file_type=existing_resume.file_type,
                message="Resume already exists"
            )
        
        # Save to database
        resume = Resume(
            user_id=user_id,
            file_path=parsed_data["file_path"],
            file_name=parsed_data["file_name"],
            file_type=parsed_data["file_type"],
            content_hash=parsed_data["content_hash"],
            parsed_data=parsed_data["parsed_data"]
        )
        
        db.add(resume)
        db.commit()
        db.refresh(resume)
        
        logger.info(f"Resume uploaded: {resume.resume_id}")
        
        return ResumeUploadResponse(
            resume_id=resume.resume_id,
            file_name=resume.file_name,
            file_type=resume.file_type,
            message="Resume uploaded successfully"
        )
        
    except Exception as e:
        logger.error(f"Resume upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process resume: {str(e)}"
        )


@router.post("/analyze/{resume_id}", response_model=ResumeAnalysisResponse)
async def analyze_resume(
    resume_id: UUID,
    db: Session = Depends(get_db),
    # user_id: UUID = Depends(get_current_user)  # TODO: Add authentication
):
    """Analyze resume and extract role information."""
    # Get resume
    resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    
    try:
        # Read resume text (from parsed data or file)
        resume_text = ""
        if resume.parsed_data and "text_content" in resume.parsed_data:
            resume_text = resume.parsed_data.get("text_content", "")
        else:
            # Read from file if not in parsed_data
            from pathlib import Path
            file_path = Path(resume.file_path)
            if file_path.exists():
                if resume.file_type == "pdf":
                    resume_text = resume_parser._extract_text_pdf(file_path)
                else:
                    resume_text = resume_parser._extract_text_docx(file_path)
        
        # Analyze with LLM (with caching)
        analysis = role_extractor.analyze_resume(
            resume_text=resume_text,
            resume_hash=resume.content_hash
        )
        
        # Update resume_id in response
        analysis.resume_id = resume.resume_id
        
        # Save suggested roles to database
        for role_match in analysis.suggested_roles:
            role_match_db = RoleMatchModel(
                resume_id=resume.resume_id,
                role_title=role_match.role_title,
                confidence_score=role_match.confidence_score,
                is_confirmed=False
            )
            db.add(role_match_db)
        
        db.commit()
        
        logger.info(f"Resume analyzed: {resume_id}")
        
        return analysis
        
    except Exception as e:
        logger.error(f"Resume analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze resume: {str(e)}"
        )


@router.get("/roles/{resume_id}")
async def get_suggested_roles(
    resume_id: UUID,
    db: Session = Depends(get_db)
):
    """Get suggested roles for resume."""
    resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    
    role_matches = db.query(RoleMatchModel).filter(
        RoleMatchModel.resume_id == resume_id
    ).all()
    
    return [
        {
            "role_match_id": str(rm.role_match_id),
            "role_title": rm.role_title,
            "confidence_score": rm.confidence_score,
            "is_confirmed": rm.is_confirmed
        }
        for rm in role_matches
    ]


@router.post("/roles/confirm", response_model=RoleConfirmationResponse)
async def confirm_role(
    request: RoleConfirmationRequest,
    resume_id: UUID,
    db: Session = Depends(get_db)
):
    """Confirm a role match."""
    # Find role match
    role_match = db.query(RoleMatchModel).filter(
        RoleMatchModel.resume_id == resume_id,
        RoleMatchModel.role_title == request.role_title
    ).first()
    
    if not role_match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role match not found"
        )
    
    role_match.is_confirmed = request.is_confirmed
    db.commit()
    
    return RoleConfirmationResponse(
        role_match_id=role_match.role_match_id,
        role_title=role_match.role_title,
        is_confirmed=role_match.is_confirmed,
        message="Role confirmed successfully" if request.is_confirmed else "Role confirmation removed"
    )
