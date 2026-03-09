"""Pytest configuration and shared fixtures.

Key design decision: we use SQLite in-memory for speed + no Docker dependency.
SQLite doesn't understand PostgreSQL-specific types (JSONB, UUID, pgvector),
so we register type adapters that downcast them to SQLite-compatible equivalents
BEFORE creating the in-memory schema.
"""

import io
import uuid
import pytest
from unittest.mock import Mock, patch
from sqlalchemy import create_engine, event, String, Text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB


# ── SQLite compatibility: downcast PG-specific types ────────────────────────────
#
# SQLAlchemy renders column types based on the dialect.  For JSONB and PG UUID
# we register dialect-level type overrides so SQLite sees plain JSON / TEXT.

def _patch_models_for_sqlite():
    """
    Walk every mapped table in Base.metadata and replace JSONB → JSON,
    UUID → String(36), and Vector → Text so SQLite can create them.
    Must be called BEFORE Base.metadata.create_all().
    """
    from packages.database.models import Base
    from sqlalchemy import JSON as SA_JSON
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB

    try:
        from pgvector.sqlalchemy import Vector
        has_vector = True
    except ImportError:
        has_vector = False

    for table in Base.metadata.tables.values():
        for col in table.columns:
            t = col.type
            if isinstance(t, (PG_JSONB,)):
                col.type = SA_JSON()
            elif isinstance(t, PG_UUID):
                col.type = String(36)
            elif has_vector and isinstance(t, Vector):
                col.type = Text()


# ── In-memory SQLite engine ────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    from packages.database.models import Base

    # Patch PG-specific types BEFORE creating schema
    _patch_models_for_sqlite()

    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def db(engine):
    """Fresh DB session per test, fully rolled back after."""
    connection  = engine.connect()
    transaction = connection.begin()
    Session     = sessionmaker(bind=connection)
    session     = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ── Redis mock ────────────────────────────────────────────────────────────────

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


# ── Reusable test data helpers ────────────────────────────────────────────────

@pytest.fixture
def mock_openai():
    import json
    client   = Mock()
    response = Mock()
    response.choices                     = [Mock()]
    response.choices[0].message         = Mock()
    response.choices[0].message.content = json.dumps({
        "role": "Senior GenAI Engineer",
        "seniority": "Senior",
        "employment_type": "Full-time",
        "location_type": "Hybrid",
        "must_have_skills": ["Python", "LangChain", "Azure OpenAI"],
        "nice_to_have_skills": ["Kubernetes"],
        "responsibilities": ["Build LLM pipelines"],
        "ats_keywords": ["GenAI", "RAG"],
        "red_flags": [],
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
def user_id():
    return uuid.uuid4()


@pytest.fixture
def minimal_docx_bytes():
    """Smallest valid-looking docx (ZIP magic bytes)."""
    return b"PK\x03\x04" + b"\x00" * 26


@pytest.fixture
def resume_text():
    return """
    Vijay Reddybathula | Senior GenAI Engineer | Dallas, TX

    EXPERIENCE
    Blue Yonder — Senior GenAI Engineer (2022–present)
    - Built RAG pipelines using LangChain and Azure OpenAI
    - Deployed LLM microservices on Azure AKS
    - Python, FastAPI, PostgreSQL, Redis

    SKILLS
    Languages:  Python, TypeScript
    Frameworks: LangChain, FastAPI, React
    Cloud:      Azure, AWS
    """


@pytest.fixture
def sample_job_text():
    return """
    Senior GenAI Engineer — Deloitte (Dallas, TX · Hybrid)
    Salary: $150,000 – $200,000

    Must Have: 5+ years Python, LangChain, Azure OpenAI
    Nice to Have: Kubernetes, MLOps
    Responsibilities: Design LLM applications, lead architecture discussions.
    """
