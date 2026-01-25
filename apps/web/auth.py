"""Authentication utilities for API endpoints."""

from fastapi import Depends, HTTPException, status, Header
from uuid import UUID
from typing import Optional


async def get_current_user(
    x_user_id: Optional[str] = Header(None),
) -> UUID:
    """
    Extract user_id from X-User-ID header.

    In a production environment, this would validate JWT tokens or similar.
    For now, we expect the client to send X-User-ID header with the UUID.

    Args:
        x_user_id: User ID from X-User-ID header

    Returns:
        UUID: The user ID

    Raises:
        HTTPException: If user_id is not provided or invalid
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-ID header. Please provide your user ID.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(x_user_id)
        return user_id
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-User-ID header. Must be a valid UUID.",
            headers={"WWW-Authenticate": "Bearer"},
        )
