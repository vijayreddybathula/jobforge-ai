"""Resume API endpoints — user_id from auth."""

import hashlib
import io
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.web.auth import get_current_user
from packages.common.logging import get_logger
from packages.database.connection import get_db
from packages.database.models import Resume, RoleMatch, UserProfile
from services.resume_analyzer.role_extractor import RoleExtractor

try:
    from azure.storage.blob import BlobServiceClient
    import os
    AZURE_CONN = os.getenv("AZURE_BLOB_CONNECTION_STRING")
    AZURE_CONTAINER = "resumes"
except ImportError:
    AZURE_CONN = None

logger = get_logger(__name__)
router = APIRouter(prefix="/resume", tags=["resume"])
role_extractor = RoleExtractor()


class RoleConfirmRequest(BaseModel):
    resume_id: UUID
    confirmed_roles: List[str]


# ── List resumes for current user ─────────────────────────────────────────────

@router.get("/", summary="List all resumes for current user")
async def list_resumes(
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns only the authenticated user's resumes. Never returns another user's."""
    resumes = (
        db.query(Resume)
        .filter(Resume.user_id == current_user_id)
        .order_by(Resume.created_at.desc())
        .all()
    )
    return [
        {
            "resume_id": str(r.resume_id),
            "file_name": r.file_name,
            "file_type": r.file_type,
            "version": r.version,
            "created_at": r.created_at.isoformat(),
            "has_parsed_data": bool(r.parsed_data),
        }
        for r in resumes
    ]


# ── Upload ─────────────────────────────────────────────────────────────────────

@router.post("/upload", status_code=201, summary="Upload a resume")
async def upload_resume(
    file: UploadFile = File(...),
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a resume. Deduplicates by content hash. Scoped to current user."""
    if file.content_type not in (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are accepted.")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")

    content_hash = hashlib.sha256(content).hexdigest()

    # Dedup check — but only within this user's resumes
    existing = (
        db.query(Resume)
        .filter(Resume.user_id == current_user_id, Resume.content_hash == content_hash)
        .first()
    )
    if existing:
        return {
            "resume_id": str(existing.resume_id),
            "message": "Identical resume already uploaded.",
            "duplicate": True,
            "file_name": existing.file_name,
        }

    # Version number for this user
    version = (
        db.query(Resume).filter(Resume.user_id == current_user_id).count() + 1
    )

    # Upload to Azure Blob
    file_ext = "pdf" if "pdf" in (file.content_type or "") else "docx"
    blob_name = f"{current_user_id}/{content_hash}.{file_ext}"
    file_path = blob_name

    if AZURE_CONN:
        try:
            blob_client = BlobServiceClient.from_connection_string(AZURE_CONN)
            container = blob_client.get_container_client(AZURE_CONTAINER)
            container.upload_blob(name=blob_name, data=io.BytesIO(content), overwrite=True)
        except Exception as e:
            logger.warning(f"Azure upload failed, storing path only: {e}")

    resume = Resume(
        user_id=current_user_id,
        version=version,
        file_path=file_path,
        file_name=file.filename or f"resume_v{version}.{file_ext}",
        file_type=file_ext,
        content_hash=content_hash,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    logger.info(f"Resume uploaded: user={current_user_id} resume={resume.resume_id} v{version}")
    return {
        "resume_id": str(resume.resume_id),
        "file_name": resume.file_name,
        "version": version,
        "message": "Resume uploaded. Call POST /resume/analyze/{id} to extract roles.",
        "duplicate": False,
    }


# ── Analyze ────────────────────────────────────────────────────────────────────

@router.post("/analyze/{resume_id}", summary="Analyze resume with LLM")
async def analyze_resume(
    resume_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extract role matches from resume using Azure OpenAI. Ownership-checked."""
    resume = (
        db.query(Resume)
        .filter(Resume.resume_id == resume_id, Resume.user_id == current_user_id)
        .first()
    )
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found or not yours.")

    if AZURE_CONN:
        try:
            blob_client = BlobServiceClient.from_connection_string(AZURE_CONN)
            blob = blob_client.get_blob_client(container=AZURE_CONTAINER, blob=resume.file_path)
            file_bytes = blob.download_blob().readall()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not retrieve resume file: {e}")
    else:
        raise HTTPException(status_code=500, detail="Azure Blob Storage not configured.")

    role_matches = role_extractor.extract_roles(file_bytes, resume.file_type)

    # Clear old role matches for this resume
    db.query(RoleMatch).filter(RoleMatch.resume_id == resume_id).delete()

    for match in role_matches:
        rm = RoleMatch(
            resume_id=resume_id,
            role_title=match["role"],
            confidence_score=match.get("confidence", 80),
            is_confirmed=False,
        )
        db.add(rm)

    db.commit()
    logger.info(f"Resume analyzed: {resume_id}, {len(role_matches)} roles found")

    return {
        "resume_id": str(resume_id),
        "roles_found": len(role_matches),
        "message": "Analysis complete. Call GET /resume/roles/{id} to review.",
    }


# ── Get roles ──────────────────────────────────────────────────────────────────

@router.get("/roles/{resume_id}", summary="Get extracted role matches")
async def get_roles(
    resume_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get role suggestions for resume. Ownership-checked."""
    resume = (
        db.query(Resume)
        .filter(Resume.resume_id == resume_id, Resume.user_id == current_user_id)
        .first()
    )
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found or not yours.")

    roles = db.query(RoleMatch).filter(RoleMatch.resume_id == resume_id).all()
    return {
        "resume_id": str(resume_id),
        "roles": [
            {
                "role_match_id": str(r.role_match_id),
                "role_title": r.role_title,
                "confidence_score": r.confidence_score,
                "is_confirmed": r.is_confirmed,
            }
            for r in roles
        ],
    }


# ── Confirm roles ──────────────────────────────────────────────────────────────

@router.post("/roles/confirm", summary="Confirm target roles")
async def confirm_roles(
    body: RoleConfirmRequest,
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark selected roles as confirmed. Ownership-checked."""
    resume = (
        db.query(Resume)
        .filter(Resume.resume_id == body.resume_id, Resume.user_id == current_user_id)
        .first()
    )
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found or not yours.")

    # Reset all, then confirm selected
    db.query(RoleMatch).filter(RoleMatch.resume_id == body.resume_id).update(
        {"is_confirmed": False}
    )
    confirmed = (
        db.query(RoleMatch)
        .filter(
            RoleMatch.resume_id == body.resume_id,
            RoleMatch.role_title.in_(body.confirmed_roles),
        )
        .all()
    )
    for r in confirmed:
        r.is_confirmed = True
    db.commit()

    return {
        "resume_id": str(body.resume_id),
        "confirmed_count": len(confirmed),
        "confirmed_roles": [r.role_title for r in confirmed],
        "next_step": f"POST /profile/build-from-resume/{body.resume_id}",
    }


# ── Delete ─────────────────────────────────────────────────────────────────────

@router.delete("/{resume_id}", summary="Delete a resume")
async def delete_resume(
    resume_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a resume and its role matches. Ownership strictly enforced."""
    resume = (
        db.query(Resume)
        .filter(Resume.resume_id == resume_id, Resume.user_id == current_user_id)
        .first()
    )
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found or not yours.")

    # Delete role matches first (FK)
    db.query(RoleMatch).filter(RoleMatch.resume_id == resume_id).delete()
    db.delete(resume)
    db.commit()

    logger.info(f"Resume deleted: {resume_id} by user {current_user_id}")
    return {"message": "Resume deleted.", "resume_id": str(resume_id)}
