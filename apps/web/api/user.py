"""User management API — signup, login, profile."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from uuid import UUID
import bcrypt

from packages.database.connection import get_db
from packages.database.models import User
from apps.web.auth import get_current_user
from packages.common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


# ── Request / Response schemas ───────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    user_id: UUID
    email: str
    full_name: str | None
    is_active: bool


class LoginResponse(BaseModel):
    user_id: UUID
    email: str
    full_name: str | None
    message: str = "Login successful"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=LoginResponse, status_code=201)
async def signup(body: SignupRequest, db: Session = Depends(get_db)):
    """
    Create a new user account.
    Auto-logs in on success — returns user_id for frontend to store.
    Redirects to /resume after signup (onboarding flow).
    """
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    if len(body.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters.",
        )

    user = User(
        email=body.email,
        hashed_password=_hash_password(body.password),
        full_name=body.full_name,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"New user registered: {user.email} ({user.user_id})")

    return LoginResponse(
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        message="Account created. Welcome to JobForge AI!",
    )


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with email + password.
    Returns user_id for frontend to store in localStorage as jf_session.
    All subsequent API calls must include X-User-ID: <user_id> header.
    """
    user = db.query(User).filter(User.email == body.email).first()

    if not user:
        # Use a generic message — don't reveal whether email exists
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact support.",
        )

    if not _verify_password(body.password, user.hashed_password):
        logger.warning(f"Failed login attempt for email: {body.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    logger.info(f"User logged in: {user.email} ({user.user_id})")

    return LoginResponse(
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the currently authenticated user's profile."""
    user = db.query(User).filter(User.user_id == current_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
    )


@router.get("/", tags=["users"])
async def list_users(db: Session = Depends(get_db)):
    """List all users (dev/admin only — remove or protect in production)."""
    users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
    return [
        {"user_id": str(u.user_id), "email": u.email, "full_name": u.full_name}
        for u in users
    ]
