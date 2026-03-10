"""Pytest configuration and shared fixtures.

SQLite in-memory DB for speed.  PG-specific column types (JSONB, UUID,
Vector) are downcast to SQLite equivalents before schema creation.
"""

import uuid
import pytest
from unittest.mock import Mock, patch
from sqlalchemy import create_engine, String, Text
from sqlalchemy import JSON as SA_JSON
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Downcast PG-specific column types so SQLite can create the schema
# ---------------------------------------------------------------------------

def _patch_models_for_sqlite(Base):
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB
    try:
        from pgvector.sqlalchemy import Vector
    except ImportError:
        Vector = None

    for table in Base.metadata.tables.values():
        for col in table.columns:
            t = col.type
            if isinstance(t, PG_JSONB):
                col.type = SA_JSON()
            elif isinstance(t, PG_UUID):
                col.type = String(36)
            elif Vector and isinstance(t, Vector):
                col.type = Text()


# ---------------------------------------------------------------------------
# Single shared engine + session factory (module scope so TestClient can reuse)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def engine():
    from packages.database.models import Base
    _patch_models_for_sqlite(Base)
    e = create_engine("sqlite:///:memory:",
                      connect_args={"check_same_thread": False})
    Base.metadata.create_all(e)
    return e


@pytest.fixture(scope="session")
def SessionFactory(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture
def db(SessionFactory):
    """Per-test DB session; changes are rolled back after each test."""
    session = SessionFactory()
    yield session
    session.rollback()
    session.close()


# ---------------------------------------------------------------------------
# Redis mock
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def setup_redis():
    from packages.common import redis_cache
    mock_client = Mock()
    mock_client.ping.return_value      = True
    mock_client.get.return_value       = None
    mock_client.set.return_value       = True
    mock_client.delete.return_value    = True
    mock_client.exists.return_value    = False
    mock_client.increment.return_value = 1
    mock_client.sismember.return_value = False
    mock_client.sadd.return_value      = 1
    with patch("redis.Redis") as mock_redis_class:
        mock_redis_class.return_value = mock_client
        redis_cache.init_redis_cache()
    yield


@pytest.fixture
def mock_redis():
    cache = Mock()
    cache.get.return_value            = None
    cache.set.return_value            = True
    cache.delete.return_value         = True
    cache._is_available.return_value  = True
    cache.exists.return_value         = False
    cache.increment.return_value      = 1
    cache.is_in_set.return_value      = False
    cache.add_to_set.return_value     = True
    return cache


# ---------------------------------------------------------------------------
# Shared test-data helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_openai():
    import json
    client   = Mock()
    response = Mock()
    response.choices                     = [Mock()]
    response.choices[0].message         = Mock()
    response.choices[0].message.content = json.dumps({
        "role": "Senior GenAI Engineer", "seniority": "Senior",
        "employment_type": "Full-time", "location_type": "Hybrid",
        "must_have_skills": ["Python", "LangChain", "Azure OpenAI"],
        "nice_to_have_skills": ["Kubernetes"],
        "responsibilities": ["Build LLM pipelines"],
        "ats_keywords": ["GenAI", "RAG"], "red_flags": [],
        "salary_range": {"min": 150000, "max": 200000, "currency": "USD"},
    })
    client.chat.completions.create.return_value = response
    return client


@pytest.fixture
def mock_blob():
    blob = Mock()
    blob.upload_blob.return_value = Mock()
    blob.url = "https://blob.example.com/resumes/test.docx"
    container = Mock()
    container.get_blob_client.return_value = blob
    service = Mock()
    service.get_container_client.return_value = container
    return service


@pytest.fixture
def sample_job_text():
    return (
        "Senior GenAI Engineer \u2014 Deloitte (Dallas, TX \u00b7 Hybrid)\n"
        "Salary: $150,000 \u2013 $200,000\n"
        "Must Have: Python, LangChain, Azure OpenAI\n"
        "Nice to Have: Kubernetes\n"
        "Responsibilities: Design LLM applications."
    )
