"""Pytest configuration and shared fixtures."""

import io
import uuid
import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from packages.database.connection import Base, init_database
from packages.common import redis_cache


# ── In-memory SQLite DB (fast, no Docker needed) ──────────────────────────────

@pytest.fixture(scope="session")
def engine():
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def db(engine):
    """Fresh DB session per test, rolled back after."""
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
    mock_client = Mock()
    mock_client.ping.return_value    = True
    mock_client.get.return_value     = None
    mock_client.set.return_value     = True
    mock_client.delete.return_value  = True
    mock_client.exists.return_value  = False
    mock_client.increment.return_value = 1
    mock_client.sismember.return_value = False
    mock_client.sadd.return_value    = 1
    with patch("redis.Redis") as mock_redis_class:
        mock_redis_class.return_value = mock_client
        redis_cache.init_redis_cache()
    yield


@pytest.fixture
def mock_redis():
    cache = Mock()
    cache.get.return_value           = None
    cache.set.return_value           = True
    cache.delete.return_value        = True
    cache._is_available.return_value = True
    cache.exists.return_value        = False
    cache.increment.return_value     = 1
    cache.is_in_set.return_value     = False
    cache.add_to_set.return_value    = True
    return cache


# ── Azure OpenAI mock ─────────────────────────────────────────────────────────

@pytest.fixture
def mock_openai():
    client   = Mock()
    response = Mock()
    response.choices                       = [Mock()]
    response.choices[0].message           = Mock()
    response.choices[0].message.content   = (
        '{"role": "Senior GenAI Engineer", "seniority": "Senior", '
        '"employment_type": "Full-time", "location_type": "Hybrid", '
        '"must_have_skills": ["Python", "LangChain", "Azure OpenAI"], '
        '"nice_to_have_skills": ["Kubernetes"], '
        '"responsibilities": ["Build LLM pipelines"], '
        '"ats_keywords": ["GenAI", "RAG"], '
        '"red_flags": [], '
        '"salary_range": {"min": 150000, "max": 200000, "currency": "USD"}}'
    )
    client.chat.completions.create.return_value = response
    return client


# ── Minimal Azure Blob mock ───────────────────────────────────────────────────

@pytest.fixture
def mock_blob():
    blob = Mock()
    blob.upload_blob.return_value     = Mock()
    blob.url                          = "https://blob.example.com/resumes/test.docx"
    container = Mock()
    container.get_blob_client.return_value = blob
    service   = Mock()
    service.get_container_client.return_value = container
    return service


# ── Reusable test data helpers ────────────────────────────────────────────────

@pytest.fixture
def user_id():
    return uuid.uuid4()


@pytest.fixture
def minimal_docx_bytes():
    """Smallest valid docx (ZIP magic bytes) for upload tests."""
    return b"PK\x03\x04" + b"\x00" * 26  # ZIP header — passes extension check


@pytest.fixture
def resume_text():
    return """
    Vijay Reddybathula
    Senior GenAI Engineer | Dallas, TX

    EXPERIENCE
    Blue Yonder — Senior GenAI Engineer (2022–present)
    - Built RAG pipelines using LangChain and Azure OpenAI
    - Deployed LLM microservices on Azure AKS
    - Python, FastAPI, PostgreSQL, Redis

    SKILLS
    Languages:  Python, TypeScript
    Frameworks: LangChain, FastAPI, React
    Cloud:      Azure, AWS
    Databases:  PostgreSQL, Redis, MongoDB
    """


@pytest.fixture
def sample_job_text():
    return """
    Senior GenAI Engineer — Deloitte
    Location: Dallas, TX (Hybrid)
    Salary: $150,000 – $200,000

    We are looking for a Senior GenAI Engineer to join our AI practice.

    Must Have:
    - 5+ years Python
    - Experience with LLMs and LangChain
    - Azure OpenAI or similar

    Nice to Have:
    - Kubernetes experience
    - MLOps background

    Responsibilities:
    - Design and build LLM-powered applications
    - Lead technical architecture discussions
    """
