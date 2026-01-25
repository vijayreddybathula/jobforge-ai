"""User management API endpoints."""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
from typing import List

from packages.database.connection import get_db
from packages.database.models import User
from packages.schemas.user_schema import UserCreate, UserRead
from passlib.context import CryptContext
from apps.web.auth import get_current_user

router = APIRouter(prefix="/users", tags=["users"])
# Use pbkdf2 instead of bcrypt to avoid binary compilation issues
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def get_password_hash(password: str) -> str:
    # Use pbkdf2_sha256 which doesn't require binary compilation
    return pwd_context.hash(password)


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = get_password_hash(user.password)
    new_user = User(
        email=user.email, hashed_password=hashed_password, full_name=user.full_name, is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: UUID, current_user_id: UUID = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get user profile (only own profile accessible)."""
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only view your own profile")
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID, current_user_id: UUID = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Delete user account (only own account)."""
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only delete your own account")
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return


@router.get("/", response_model=List[UserRead])
def list_users(db: Session = Depends(get_db)):
    """List all users (public endpoint)."""
    return db.query(User).all()


@router.get("/by-email/{email}", response_model=UserRead)
def get_user_by_email(email: str, db: Session = Depends(get_db)):
    """Get user by email (for sign-in purposes)."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
