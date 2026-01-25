"""Redis caching utilities."""

import json
import hashlib
from typing import Any, Optional, Callable, cast
import redis
from redis.exceptions import RedisError
import logging

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis cache manager with automatic serialization."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = True,
    ):
        """Initialize Redis connection."""
        self.client: Any = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
            decode_responses=cast(Any, decode_responses),
        )
        self._test_connection()

    def _test_connection(self) -> None:
        """Test Redis connection."""
        try:
            self.client.ping()
        except RedisError as e:
            logger.warning(f"Redis connection failed: {e}. Caching will be disabled.")
            self.client = None

    def _is_available(self) -> bool:
        """Check if Redis is available."""
        if self.client is None:
            return False
        try:
            self.client.ping()
            return True
        except RedisError:
            return False

    def _generate_key(self, prefix: str, identifier: str) -> str:
        """Generate cache key."""
        return f"{prefix}{identifier}"

    def _hash_content(self, content: str) -> str:
        """Generate hash for content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self._is_available():
            return None

        try:
            value = self.client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL."""
        if not self._is_available():
            return False

        try:
            serialized = json.dumps(value)
            self.client.setex(key, ttl, serialized)
            return True
        except (RedisError, TypeError) as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self._is_available():
            return False

        try:
            self.client.delete(key)
            return True
        except RedisError as e:
            logger.warning(f"Cache delete failed for key {key}: {e}")
            return False

    def get_or_set(
        self, key: str, value_func: Callable[..., Any], ttl: int = 3600, *args: Any, **kwargs: Any
    ) -> Any:
        """Get from cache or set using value function."""
        # Try to get from cache
        cached = self.get(key)
        if cached is not None:
            return cached

        # Generate value
        value = value_func(*args, **kwargs)

        # Store in cache
        self.set(key, value, ttl)

        return value

    def get_by_content_hash(self, prefix: str, content: str, ttl: int = 3600) -> Optional[Any]:
        """Get value by content hash."""
        content_hash = self._hash_content(content)
        key = self._generate_key(prefix, content_hash)
        return self.get(key)

    def set_by_content_hash(self, prefix: str, content: str, value: Any, ttl: int = 3600) -> bool:
        """Set value by content hash."""
        content_hash = self._hash_content(content)
        key = self._generate_key(prefix, content_hash)
        return self.set(key, value, ttl)

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter."""
        if not self._is_available():
            return None

        try:
            result: Any = self.client.incrby(key, amount)
            return result if isinstance(result, int) else None
        except RedisError as e:
            logger.warning(f"Cache increment failed for key {key}: {e}")
            return None

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self._is_available():
            return False

        try:
            return bool(self.client.exists(key))
        except RedisError:
            return False

    def add_to_set(self, key: str, value: str) -> bool:
        """Add value to Redis set."""
        if not self._is_available():
            return False

        try:
            self.client.sadd(key, value)
            return True
        except RedisError as e:
            logger.warning(f"Add to set failed for key {key}: {e}")
            return False

    def is_in_set(self, key: str, value: str) -> bool:
        """Check if value is in Redis set."""
        if not self._is_available():
            return False

        try:
            return bool(self.client.sismember(key, value))
        except RedisError:
            return False


# Global Redis cache instance (will be initialized in app startup)
redis_cache: Optional[RedisCache] = None


def get_redis_cache() -> RedisCache:
    """Get global Redis cache instance."""
    if redis_cache is None:
        raise RuntimeError("Redis cache not initialized. Call init_redis_cache() first.")
    return redis_cache


def init_redis_cache(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
    password: Optional[str] = None,
) -> RedisCache:
    """Initialize global Redis cache instance."""
    global redis_cache
    redis_cache = RedisCache(host=host, port=port, db=db, password=password)
    return redis_cache
