"""Resume API endpoints."""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
import os
from azure.storage.blob import BlobServiceClient


from packages.database.connection import get_db
from packages.database.models import Resume, RoleMatch as RoleMatchModel, User
from packages.schemas.resume import (
    ResumeUploadResponse,
    ResumeAnalysisResponse,
    RoleConfirmationRequest,
    RoleConfirmationResponse,
)
from services.resume_analyzer.resume_parser import ResumeParser
from services.resume_analyzer.role_extractor import RoleExtractor
from packages.common.logging import get_logger
from apps.web.auth import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/resume", tags=["resume"])

# Initialize services
resume_parser = ResumeParser()
role_extractor = RoleExtractor()


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload and parse resume."""
    # Initialize BlobServiceClient inside the endpoint for robustness
    AZURE_CONNECTION_STRING = os.getenv("AZURE_BLOB_CONNECTION_STRING")
    AZURE_CONTAINER = "resumes"
    if not AZURE_CONNECTION_STRING:
        logger.error("AZURE_BLOB_CONNECTION_STRING is missing or empty.")
        raise HTTPException(
            status_code=500, detail="Azure Blob Storage connection string is not configured."
        )
    try:
        # Initialize BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)

        # Ensure container exists, create if necessary
        try:
            container_client = blob_service_client.get_container_client(AZURE_CONTAINER)
            container_client.get_container_properties()
        except Exception as e:
            logger.info(f"Container {AZURE_CONTAINER} not found, creating it...")
            try:
                blob_service_client.create_container(name=AZURE_CONTAINER)
                logger.info(f"Successfully created container {AZURE_CONTAINER}")
            except Exception as create_error:
                logger.error(f"Failed to create container: {create_error}")
                raise
    except Exception as e:
        logger.error(f"Failed to initialize BlobServiceClient: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to Azure Blob Storage.")

    # Verify user exists
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_id} not found"
        )

    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided")

    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in ["pdf", "docx", "doc"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}. Supported: pdf, docx, doc",
        )

    try:
        # Read file content
        file_content = await file.read()

        # Parse resume FIRST to get content hash for deduplication check
        from datetime import datetime
        from uuid import uuid4
        from sqlalchemy import func

        parsed_data = resume_parser.parse_resume(
            file_content=file_content, file_name=file.filename, user_id=str(user_id)
        )

        # Check if resume already exists BEFORE uploading to blob
        existing_resume = (
            db.query(Resume).filter(Resume.content_hash == parsed_data["content_hash"]).first()
        )

        if existing_resume:
            return ResumeUploadResponse(
                resume_id=existing_resume.resume_id,
                file_name=existing_resume.file_name,
                file_type=existing_resume.file_type,
                message="Resume already exists",
            )

        # Only now upload to blob if it's a new resume
        # Get user name for path
        user_name = user.full_name.replace(" ", "_").lower()

        # Get next version number for this user
        max_version = (
            db.query(func.max(Resume.version)).filter(Resume.user_id == user_id).scalar() or 0
        )
        version_number = max_version + 1

        # Generate timestamp and resume ID
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        resume_id = uuid4()

        # Construct blob path - use version number for readability
        # NOTE: Don't include container name in blob_path, only the relative path within container
        blob_path = f"{user_id}_{user_name}/{version_number}_{timestamp}/{file.filename}"

        blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER, blob=blob_path)
        blob_client.upload_blob(file_content, overwrite=True)

        # Save to database
        resume = Resume(
            resume_id=resume_id,
            user_id=user_id,
            version=version_number,  # Store version number
            file_path=blob_path,  # Store clean blob path
            file_name=file.filename,
            file_type=file_ext,
            content_hash=parsed_data["content_hash"],
            parsed_data=parsed_data["parsed_data"],
        )

        db.add(resume)
        db.commit()
        db.refresh(resume)

        logger.info(f"Resume uploaded: {resume.resume_id}")

        return ResumeUploadResponse(
            resume_id=resume.resume_id,
            file_name=resume.file_name,
            file_type=resume.file_type,
            message="Resume uploaded to Azure Blob Storage",
        )

    except Exception as e:
        logger.error(f"Resume upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process resume: {str(e)}",
        )


@router.post("/analyze/{resume_id}", response_model=ResumeAnalysisResponse)
async def analyze_resume(
    resume_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyze resume and extract role information."""
    # Get resume
    resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    # Verify the resume belongs to the user
    if resume.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to analyze this resume",
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
            resume_text=resume_text, resume_hash=resume.content_hash
        )

        # Update resume_id in response
        analysis.resume_id = resume.resume_id

        # Save suggested roles to database
        for role_match in analysis.suggested_roles:
            role_match_db = RoleMatchModel(
                resume_id=resume.resume_id,
                role_title=role_match.role_title,
                confidence_score=role_match.confidence_score,
                is_confirmed=False,
            )
            db.add(role_match_db)

        db.commit()

        logger.info(f"Resume analyzed: {resume_id}")

        return analysis

    except Exception as e:
        logger.error(f"Resume analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze resume: {str(e)}",
        )


@router.get("/roles/{resume_id}")
async def get_suggested_roles(
    resume_id: UUID, user_id: UUID = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get suggested roles for resume (user's own resumes only)."""
    resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    # Verify resume ownership
    if resume.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this resume",
        )

    role_matches = db.query(RoleMatchModel).filter(RoleMatchModel.resume_id == resume_id).all()

    return [
        {
            "role_match_id": str(rm.role_match_id),
            "role_title": rm.role_title,
            "confidence_score": rm.confidence_score,
            "is_confirmed": rm.is_confirmed,
        }
        for rm in role_matches
    ]


@router.post("/roles/confirm", response_model=RoleConfirmationResponse)
async def confirm_role(
    request: RoleConfirmationRequest,
    resume_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirm a role match (user's own resumes only)."""
    resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    # Verify resume ownership
    if resume.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this resume",
        )

    # Find role match
    role_match = (
        db.query(RoleMatchModel)
        .filter(
            RoleMatchModel.resume_id == resume_id, RoleMatchModel.role_title == request.role_title
        )
        .first()
    )

    if not role_match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role match not found")

    role_match.is_confirmed = request.is_confirmed
    db.commit()

    return RoleConfirmationResponse(
        role_match_id=role_match.role_match_id,
        role_title=role_match.role_title,
        is_confirmed=role_match.is_confirmed,
        message=(
            "Role confirmed successfully" if request.is_confirmed else "Role confirmation removed"
        ),
    )


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a resume (user's own resumes only)."""
    resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    # Verify resume ownership
    if resume.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this resume",
        )

    try:
        # Delete from Azure Blob Storage if path is available
        if resume.file_path:
            AZURE_CONNECTION_STRING = os.getenv("AZURE_BLOB_CONNECTION_STRING")
            AZURE_CONTAINER = "resumes"
            if AZURE_CONNECTION_STRING:
                try:
                    blob_service_client = BlobServiceClient.from_connection_string(
                        AZURE_CONNECTION_STRING
                    )
                    blob_client = blob_service_client.get_blob_client(
                        container=AZURE_CONTAINER, blob=resume.file_path
                    )
                    blob_client.delete_blob()
                    logger.info(f"Deleted resume from Azure: {resume.file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete resume from Azure: {e}")

        # Delete associated role matches
        db.query(RoleMatchModel).filter(RoleMatchModel.resume_id == resume_id).delete()

        # Delete resume from database
        db.delete(resume)
        db.commit()

        logger.info(f"Resume deleted: {resume_id}")
        return None

    except Exception as e:
        logger.error(f"Resume deletion failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete resume: {str(e)}",
        )


@router.get("/{resume_id}")
async def get_resume(
    resume_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get resume details (user's own resumes only)."""
    resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    # Verify resume ownership
    if resume.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this resume",
        )

    return {
        "resume_id": str(resume.resume_id),
        "user_id": str(resume.user_id),
        "file_name": resume.file_name,
        "file_type": resume.file_type,
        "file_path": resume.file_path,
        "created_at": resume.created_at,
    }


@router.get("")
async def list_user_resumes(
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all resumes for the authenticated user."""
    resumes = db.query(Resume).filter(Resume.user_id == user_id).all()

    return [
        {
            "resume_id": str(resume.resume_id),
            "user_id": str(resume.user_id),
            "file_name": resume.file_name,
            "file_type": resume.file_type,
            "file_path": resume.file_path,
            "created_at": resume.created_at,
        }
        for resume in resumes
    ]
