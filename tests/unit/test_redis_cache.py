"""Unit tests for Redis cache."""

import pytest
from packages.common.redis_cache import RedisCache


def test_redis_cache_get_set(mock_redis, monkeypatch):
    """Test Redis cache get and set."""
    monkeypatch.setattr("packages.common.redis_cache.RedisCache.client", mock_redis)
    
    cache = RedisCache()
    cache.client = mock_redis
    
    # Test set
    result = cache.set("test_key", {"data": "value"}, ttl=3600)
    assert result is True
    
    # Test get
    mock_redis.get.return_value = '{"data": "value"}'
    result = cache.get("test_key")
    assert result == {"data": "value"}


def test_redis_cache_fallback(mock_redis):
    """Test Redis cache fallback when unavailable."""
    cache = RedisCache()
    cache.client = None
    
    # Should return None without error
    result = cache.get("test_key")
    assert result is None
    
    # Set should return False without error
    result = cache.set("test_key", "value")
    assert result is False
