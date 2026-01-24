"""Session management utilities using Redis."""

from typing import Optional, Dict, Any
import json
import secrets
from datetime import datetime, timedelta
from packages.common.redis_cache import get_redis_cache
from packages.common.logging import get_logger

logger = get_logger(__name__)


class SessionManager:
    """Redis-based session manager."""
    
    def __init__(self, ttl: int = 1800):  # 30 minutes default
        """Initialize session manager.
        
        Args:
            ttl: Session timeout in seconds
        """
        self.cache = get_redis_cache()
        self.ttl = ttl
        self.key_prefix = "session:"
    
    def _get_key(self, session_id: str) -> str:
        """Generate session key."""
        return f"{self.key_prefix}{session_id}"
    
    def create_session(self, user_id: str, data: Optional[Dict[str, Any]] = None) -> str:
        """Create new session.
        
        Args:
            user_id: User ID
            data: Additional session data
        
        Returns:
            Session ID
        """
        session_id = secrets.token_urlsafe(32)
        key = self._get_key(session_id)
        
        session_data = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "data": data or {}
        }
        
        if self.cache.set(key, session_data, ttl=self.ttl):
            logger.info(f"Session created: {session_id[:8]}... for user {user_id}")
            return session_id
        else:
            raise RuntimeError("Failed to create session")
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data.
        
        Args:
            session_id: Session ID
        
        Returns:
            Session data or None
        """
        key = self._get_key(session_id)
        return self.cache.get(key)
    
    def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Update session data.
        
        Args:
            session_id: Session ID
            data: Data to update
        
        Returns:
            True if updated successfully
        """
        session = self.get_session(session_id)
        if session is None:
            return False
        
        session["data"].update(data)
        session["updated_at"] = datetime.utcnow().isoformat()
        
        key = self._get_key(session_id)
        return self.cache.set(key, session, ttl=self.ttl)
    
    def extend_session(self, session_id: str) -> bool:
        """Extend session TTL.
        
        Args:
            session_id: Session ID
        
        Returns:
            True if extended successfully
        """
        session = self.get_session(session_id)
        if session is None:
            return False
        
        key = self._get_key(session_id)
        return self.cache.set(key, session, ttl=self.ttl)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session.
        
        Args:
            session_id: Session ID
        
        Returns:
            True if deleted successfully
        """
        key = self._get_key(session_id)
        return self.cache.delete(key)
    
    def get_user_id(self, session_id: str) -> Optional[str]:
        """Get user ID from session.
        
        Args:
            session_id: Session ID
        
        Returns:
            User ID or None
        """
        session = self.get_session(session_id)
        if session:
            return session.get("user_id")
        return None


class BrowserSessionManager(SessionManager):
    """Manager for browser automation sessions."""
    
    def __init__(self):
        super().__init__(ttl=1800)  # 30 minutes
        self.key_prefix = "browser_session:"
    
    def save_browser_state(
        self,
        session_id: str,
        cookies: list,
        local_storage: Dict[str, Any],
        user_id: str
    ) -> bool:
        """Save browser session state.
        
        Args:
            session_id: Session ID
            cookies: Browser cookies
            local_storage: Local storage data
            user_id: User ID
        
        Returns:
            True if saved successfully
        """
        session_data = {
            "user_id": user_id,
            "cookies": cookies,
            "local_storage": local_storage,
            "created_at": datetime.utcnow().isoformat(),
        }
        
        key = self._get_key(session_id)
        return self.cache.set(key, session_data, ttl=self.ttl)
    
    def get_browser_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get browser session state.
        
        Args:
            session_id: Session ID
        
        Returns:
            Browser state or None
        """
        return self.get_session(session_id)
