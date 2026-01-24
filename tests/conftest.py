"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import Mock, MagicMock
from packages.database.connection import init_database, get_db
from packages.common.redis_cache import init_redis_cache


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
