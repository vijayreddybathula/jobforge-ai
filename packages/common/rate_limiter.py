"""Redis-based rate limiting utilities."""

import time
from typing import Optional
from packages.common.redis_cache import get_redis_cache
from packages.common.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Redis-based distributed rate limiter."""

    def __init__(self, key_prefix: str = "ratelimit:", window: int = 3600):
        """Initialize rate limiter.

        Args:
            key_prefix: Prefix for Redis keys
            window: Time window in seconds
        """
        self.key_prefix = key_prefix
        self.window = window
        self.cache = get_redis_cache()

    def _get_key(self, identifier: str) -> str:
        """Generate Redis key."""
        return f"{self.key_prefix}{identifier}"

    def check_rate_limit(self, identifier: str, max_requests: int, window: Optional[int] = None):
        """Check if rate limit is exceeded.

        Args:
            identifier: Unique identifier (e.g., source type, user ID)
            max_requests: Maximum requests allowed in window
            window: Time window in seconds (defaults to self.window)

        Returns:
            Tuple of (is_allowed, current_count, remaining)
        """
        window = window or self.window
        key = self._get_key(identifier)

        if not self.cache._is_available():
            # If Redis is unavailable, allow request but log warning
            logger.warning(f"Redis unavailable, allowing request for {identifier}")
            return True, 0, max_requests

        try:
            current_time = int(time.time())
            window_start = current_time - window

            # Get current count
            count = self.cache.client.get(key)
            if count is None:
                count = 0
            else:
                count = int(count)

            # Check if limit exceeded
            if count >= max_requests:
                remaining = 0
                return False, count, remaining

            # Increment counter
            new_count = self.cache.increment(key, 1)
            if new_count is None:
                new_count = count + 1

            # Set expiration on first request
            if count == 0:
                self.cache.client.expire(key, window)

            remaining = max(0, max_requests - new_count)
            return True, new_count, remaining

        except Exception as e:
            logger.error(f"Rate limit check failed for {identifier}: {e}")
            # Fail open - allow request if rate limiting fails
            return True, 0, max_requests

    def reset(self, identifier: str) -> bool:
        """Reset rate limit for identifier."""
        key = self._get_key(identifier)
        return self.cache.delete(key)

    def get_remaining(self, identifier: str, max_requests: int) -> int:
        """Get remaining requests for identifier."""
        key = self._get_key(identifier)

        if not self.cache._is_available():
            return max_requests

        try:
            count = self.cache.client.get(key)
            if count is None:
                return max_requests
            count = int(count)
            return max(0, max_requests - count)
        except Exception as e:
            logger.error(f"Get remaining failed for {identifier}: {e}")
            return max_requests


class DistributedLock:
    """Redis-based distributed lock."""

    def __init__(self, key: str, timeout: int = 60):
        """Initialize distributed lock.

        Args:
            key: Lock key
            timeout: Lock timeout in seconds
        """
        self.key = f"lock:{key}"
        self.timeout = timeout
        self.cache = get_redis_cache()
        self.lock_value = None

    def acquire(self, blocking: bool = True, timeout: Optional[int] = None) -> bool:
        """Acquire lock.

        Args:
            blocking: Whether to block until lock is acquired
            timeout: Maximum time to wait for lock

        Returns:
            True if lock acquired, False otherwise
        """
        if not self.cache._is_available():
            logger.warning("Redis unavailable, lock acquisition failed")
            return False

        import uuid

        self.lock_value = str(uuid.uuid4())
        timeout = timeout or self.timeout
        end_time = time.time() + timeout

        while True:
            # Try to acquire lock using SET NX EX
            acquired = self.cache.client.set(self.key, self.lock_value, nx=True, ex=self.timeout)

            if acquired:
                return True

            if not blocking or time.time() >= end_time:
                return False

            time.sleep(0.1)

    def release(self) -> bool:
        """Release lock."""
        if not self.cache._is_available() or self.lock_value is None:
            return False

        try:
            # Lua script to ensure we only delete our own lock
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = self.cache.client.eval(lua_script, 1, self.key, self.lock_value)
            return bool(result)
        except Exception as e:
            logger.error(f"Lock release failed: {e}")
            return False

    def __enter__(self):
        """Context manager entry."""
        if not self.acquire():
            raise RuntimeError(f"Failed to acquire lock: {self.key}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
