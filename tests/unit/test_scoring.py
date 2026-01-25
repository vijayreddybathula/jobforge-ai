"""Unit tests for scoring service."""

import pytest
from services.scoring.scoring_service import ScoringService
from packages.schemas.jd_schema import ParsedJD, SeniorityLevel, EmploymentType, LocationType


def test_score_core_skills():
    """Test core skill scoring."""
    service = ScoringService()

    required_skills = ["Python", "FastAPI", "PostgreSQL"]
    user_skills = {
        "languages": ["Python", "JavaScript"],
        "frameworks": ["FastAPI", "React"],
        "data": ["PostgreSQL"],
    }

    score = service._score_core_skills(required_skills, user_skills)
    assert 0 <= score <= 100
    assert score > 50  # Should have good match


def test_determine_verdict():
    """Test verdict determination."""
    service = ScoringService()

    assert service._determine_verdict(45) == "SKIP"
    assert service._determine_verdict(60) == "VALIDATE"
    assert service._determine_verdict(75) == "ASSISTED_APPLY"
    assert service._determine_verdict(90) == "ELIGIBLE_AUTO_SUBMIT"
