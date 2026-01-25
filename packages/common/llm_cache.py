"""LLM response caching utilities."""

from typing import Any, Optional, Callable
import hashlib
from packages.common.redis_cache import get_redis_cache
from packages.common.logging import get_logger

logger = get_logger(__name__)


class LLMCache:
    """Cache manager for LLM responses."""

    def __init__(self, ttl: int = 2592000):  # 30 days default
        """Initialize LLM cache.

        Args:
            ttl: Time to live in seconds
        """
        self.cache = get_redis_cache()
        self.ttl = ttl
        self.key_prefix = "llm:response:"

    def _hash_content(self, content: str) -> str:
        """Generate hash for content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_key(self, content_hash: str) -> str:
        """Generate cache key."""
        return f"{self.key_prefix}{content_hash}"

    def get(self, content: str) -> Optional[Any]:
        """Get cached LLM response.

        Args:
            content: Input content (prompt, JD text, etc.)

        Returns:
            Cached response or None
        """
        content_hash = self._hash_content(content)
        key = self._get_key(content_hash)
        return self.cache.get(key)

    def set(self, content: str, response: Any) -> bool:
        """Cache LLM response.

        Args:
            content: Input content
            response: LLM response to cache

        Returns:
            True if cached successfully
        """
        content_hash = self._hash_content(content)
        key = self._get_key(content_hash)
        return self.cache.set(key, response, ttl=self.ttl)

    def get_or_call(
        self, content: str, llm_func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Get from cache or call LLM function.

        Args:
            content: Input content
            llm_func: Function to call if not cached
            *args, **kwargs: Arguments to pass to llm_func

        Returns:
            Cached or fresh LLM response
        """
        # Try cache first
        cached = self.get(content)
        if cached is not None:
            logger.debug(f"Cache hit for LLM request (hash: {self._hash_content(content)[:8]})")
            return cached

        # Call LLM function
        logger.debug(f"Cache miss, calling LLM (hash: {self._hash_content(content)[:8]})")
        response = llm_func(*args, **kwargs)

        # Cache response
        self.set(content, response)

        return response

    def invalidate(self, content: str) -> bool:
        """Invalidate cache for content."""
        content_hash = self._hash_content(content)
        key = self._get_key(content_hash)
        return self.cache.delete(key)


# Specialized caches for different use cases
class JDParseCache(LLMCache):
    """Cache for JD parsing results."""

    def __init__(self):
        super().__init__(ttl=2592000)  # 30 days
        self.key_prefix = "jd:parsed:"


class ResumeAnalysisCache(LLMCache):
    """Cache for resume analysis results."""

    def __init__(self):
        super().__init__(ttl=2592000)  # 30 days
        self.key_prefix = "resume:analysis:"


class ScoringCache(LLMCache):
    """Cache for scoring results."""

    def __init__(self):
        super().__init__(ttl=604800)  # 7 days
        self.key_prefix = "score:"

    def get_score(self, job_id: str, profile_id: str) -> Optional[Any]:
        """Get cached score for job and profile."""
        key = f"{job_id}:{profile_id}"
        return self.get(key)

    def set_score(self, job_id: str, profile_id: str, score: Any) -> bool:
        """Cache score for job and profile."""
        key = f"{job_id}:{profile_id}"
        return self.set(key, score)
