"""Authentication dependency for FastAPI.

Simple model: email + password → user_id stored in localStorage on frontend.
All authenticated endpoints use Depends(get_current_user) instead of
accepting user_id as a query param (which is forgeable).

The X-User-ID header is validated against the DB on every request.
No JWT needed at this stage — the UUID itself is the session token,
validated server-side against is_active on every call.
"""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from packages.database.connection import get_db
from packages.database.models import User
from packages.common.logging import get_logger

logger = get_logger(__name__)


def get_current_user(
    x_user_id: str = Header(..., description="User UUID from login session"),
    db: Session = Depends(get_db),
) -> UUID:
    """
    Validate the X-User-ID header against the database.

    Returns the user's UUID if valid and active.
    Raises 401 if missing, malformed, not found, or inactive.

    This replaces all `user_id: UUID` query params across the API.
    After login, the frontend stores user_id in localStorage and sends
    it as a header on every request. The server validates it here.
    """
    try:
        user_uuid = UUID(x_user_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in X-User-ID header",
        )

    user = (
        db.query(User)
        .filter(User.user_id == user_uuid, User.is_active == True)  # noqa: E712
        .first()
    )

    if not user:
        logger.warning(f"Auth failed: user_id={x_user_id} not found or inactive")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account inactive. Please log in again.",
        )

    return user.user_id
