"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from packages.database.connection import init_database, get_db
from packages.common import redis_cache


@pytest.fixture(scope="session", autouse=True)
def setup_redis():
    """Initialize Redis cache for testing."""
    # Create a mock Redis connection
    mock_client = Mock()
    mock_client.ping.return_value = True
    mock_client.get.return_value = None
    mock_client.set.return_value = True
    mock_client.delete.return_value = True
    mock_client.exists.return_value = False
    mock_client.increment.return_value = 1
    mock_client.sismember.return_value = False
    mock_client.sadd.return_value = 1

    # Create a mock RedisCache instance
    with patch("redis.Redis") as mock_redis_class:
        mock_redis_class.return_value = mock_client
        # Initialize the global cache with mocked connection
        redis_cache.init_redis_cache()

    yield


@pytest.fixture
def mock_redis():
    """Mock Redis cache."""
    cache = Mock()
    cache.get.return_value = None
    cache.set.return_value = True
    cache.delete.return_value = True
    cache._is_available.return_value = True
    cache.exists.return_value = False
    cache.increment.return_value = 1
    cache.is_in_set.return_value = False
    cache.add_to_set.return_value = True
    return cache


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    return db


@pytest.fixture
def mock_openai():
    """Mock OpenAI client."""
    client = Mock()
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message = Mock()
    response.choices[0].message.content = '{"role": "Test", "seniority": "Senior"}'
    client.chat.completions.create.return_value = response
    return client
