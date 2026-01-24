"""SQLAlchemy database models."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class User(Base):
    """User model."""
    
    __tablename__ = "users"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    resumes = relationship("Resume", back_populates="user")
    user_profiles = relationship("UserProfile", back_populates="user")
    user_preferences = relationship("UserPreferences", back_populates="user")
    applications = relationship("Application", back_populates="user")


class Resume(Base):
    """Resume model."""
    
    __tablename__ = "resumes"
    
    resume_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(50))  # pdf, docx
    content_hash = Column(String(64), unique=True, index=True)
    parsed_data = Column(JSONB)  # Structured parsed resume data
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="resumes")
    role_matches = relationship("RoleMatch", back_populates="resume")


class RoleMatch(Base):
    """Role match model."""
    
    __tablename__ = "role_matches"
    
    role_match_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.resume_id"), nullable=False, index=True)
    role_title = Column(String(255), nullable=False)
    confidence_score = Column(Integer)  # 0-100
    is_confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    resume = relationship("Resume", back_populates="role_matches")


class UserProfile(Base):
    """User profile model."""
    
    __tablename__ = "user_profiles"
    
    profile_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, unique=True, index=True)
    core_roles = Column(JSONB)  # List of role titles
    skills = Column(JSONB)  # Nested structure: languages, frameworks, etc.
    approved_bullets = Column(JSONB)  # List of approved resume bullets
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="user_profiles")


class UserPreferences(Base):
    """User preferences model."""
    
    __tablename__ = "user_preferences"
    
    preferences_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, unique=True, index=True)
    visa_status = Column(String(100))
    location_preferences = Column(JSONB)  # remote/hybrid/onsite, cities
    disability_status = Column(String(100))
    disability_accommodations = Column(Text)
    salary_min_usd = Column(Integer)
    salary_max_usd = Column(Integer)
    company_size_preferences = Column(JSONB)
    industry_preferences = Column(JSONB)
    work_authorization = Column(String(100))
    other_constraints = Column(JSONB)
    is_ready = Column(Boolean, default=False)  # Profile ready for job ingestion
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="user_preferences")


class IngestionSource(Base):
    """Ingestion source configuration."""
    
    __tablename__ = "ingestion_sources"
    
    source_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    source_type = Column(String(50), nullable=False)  # linkedin, workday, glassdoor, company_portal
    source_url = Column(String(1000), nullable=False)
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_source_user_type", "user_id", "source_type"),
    )


class ScrapingSession(Base):
    """Scraping session tracking."""
    
    __tablename__ = "scraping_sessions"
    
    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_sources.source_id"), nullable=False, index=True)
    jobs_found = Column(Integer, default=0)
    jobs_ingested = Column(Integer, default=0)
    jobs_duplicates = Column(Integer, default=0)
    jobs_failed = Column(Integer, default=0)
    status = Column(String(50), default="running")  # running, completed, failed
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True))


class JobRaw(Base):
    """Raw job posting model."""
    
    __tablename__ = "jobs_raw"
    
    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source = Column(String(50), nullable=False, index=True)  # linkedin, workday, etc.
    source_url = Column(String(1000), unique=True, nullable=False, index=True)
    company = Column(String(255), index=True)
    title = Column(String(500), index=True)
    location = Column(String(255))
    posted_at = Column(DateTime(timezone=True))
    html_snapshot_path = Column(String(500))
    text_content = Column(Text)
    content_hash = Column(String(64), unique=True, index=True)
    ingest_status = Column(String(50), default="INGESTED", index=True)  # INGESTED, DUPLICATE, FAILED
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    parsed = relationship("JobParsed", back_populates="job", uselist=False)
    scores = relationship("JobScore", back_populates="job")
    applications = relationship("Application", back_populates="job")


class JobParsed(Base):
    """Parsed job description model."""
    
    __tablename__ = "jobs_parsed"
    
    parsed_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs_raw.job_id"), nullable=False, unique=True, index=True)
    parsed_json = Column(JSONB, nullable=False)
    parser_version = Column(String(50))
    parse_status = Column(String(50), default="PARSED", index=True)  # PARSED, PARSE_FAILED
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    job = relationship("JobRaw", back_populates="parsed")


class JobScore(Base):
    """Job score model."""
    
    __tablename__ = "job_scores"
    
    score_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs_raw.job_id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    total_score = Column(Integer, nullable=False, index=True)  # 0-100
    breakdown = Column(JSONB)  # Score breakdown by category
    verdict = Column(String(50), nullable=False, index=True)  # SKIP, VALIDATE, ASSISTED_APPLY, ELIGIBLE_AUTO_SUBMIT
    rationale = Column(Text)
    scoring_version = Column(String(50))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    job = relationship("JobRaw", back_populates="scores")
    
    __table_args__ = (
        Index("idx_job_user_score", "job_id", "user_id", "total_score"),
    )


class Artifact(Base):
    """Generated artifact model."""
    
    __tablename__ = "artifacts"
    
    artifact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs_raw.job_id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    artifact_type = Column(String(50), nullable=False, index=True)  # resume, answers, pitch
    path = Column(String(500), nullable=False)
    metadata = Column(JSONB)  # bullet IDs, keyword coverage, etc.
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_artifact_job_type", "job_id", "artifact_type"),
    )


class Application(Base):
    """Application tracking model."""
    
    __tablename__ = "applications"
    
    application_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs_raw.job_id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    apply_mode = Column(String(50), nullable=False)  # manual, assisted, auto
    status = Column(String(50), default="started", index=True)  # started, submitted, failed
    submitted_at = Column(DateTime(timezone=True))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    job = relationship("JobRaw", back_populates="applications")
    user = relationship("User", back_populates="applications")
    outcomes = relationship("Outcome", back_populates="application")


class Outcome(Base):
    """Application outcome model."""
    
    __tablename__ = "outcomes"
    
    outcome_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.application_id"), nullable=False, index=True)
    stage = Column(String(50), nullable=False, index=True)  # rejected, phone_screen, onsite, offer
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    source = Column(String(50))  # email, manual
    details = Column(JSONB)
    
    # Relationships
    application = relationship("Application", back_populates="outcomes")
