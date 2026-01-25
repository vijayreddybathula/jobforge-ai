"""Unit tests for Redis cache."""

import pytest
from unittest.mock import Mock, patch
from redis.exceptions import RedisError
from packages.common.redis_cache import RedisCache


@patch("redis.Redis")
def test_redis_cache_get_set(mock_redis_class):
    """Test Redis cache get and set."""
    mock_client = Mock()
    mock_client.ping.return_value = True
    mock_client.get.return_value = '{"data": "value"}'
    mock_client.set.return_value = True
    mock_redis_class.return_value = mock_client

    cache = RedisCache()

    # Test set
    result = cache.set("test_key", {"data": "value"}, ttl=3600)
    assert result is True

    # Test get
    result = cache.get("test_key")
    assert result == {"data": "value"}


@patch("redis.Redis")
def test_redis_cache_fallback(mock_redis_class):
    """Test Redis cache fallback when unavailable."""
    # Mock Redis connection to succeed but ping fails
    mock_client = Mock()
    mock_client.ping.side_effect = RedisError("Connection failed")
    mock_redis_class.return_value = mock_client

    cache = RedisCache()

    # Should return None without error when client is None (due to failed connection)
    result = cache.get("test_key")
    assert result is None

    # Set should return False without error
    result = cache.set("test_key", "value")
    assert result is False
