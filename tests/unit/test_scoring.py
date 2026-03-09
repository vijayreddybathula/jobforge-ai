"""Unit tests for scoring service."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4
from packages.schemas.jd_schema import ParsedJD, SeniorityLevel, EmploymentType, LocationType, SalaryRange
from services.scoring.scoring_service import ScoringService


class TestVerdictThresholds:
    """Ensure verdict bands stay correct after any future refactor."""

    def setup_method(self):
        self.svc = ScoringService()

    def test_skip_below_50(self):
        assert self.svc._determine_verdict(0)  == "SKIP"
        assert self.svc._determine_verdict(49) == "SKIP"

    def test_validate_50_to_69(self):
        assert self.svc._determine_verdict(50) == "VALIDATE"
        assert self.svc._determine_verdict(69) == "VALIDATE"

    def test_assisted_apply_70_to_84(self):
        assert self.svc._determine_verdict(70) == "ASSISTED_APPLY"
        assert self.svc._determine_verdict(84) == "ASSISTED_APPLY"

    def test_auto_submit_85_plus(self):
        assert self.svc._determine_verdict(85) == "ELIGIBLE_AUTO_SUBMIT"
        assert self.svc._determine_verdict(100) == "ELIGIBLE_AUTO_SUBMIT"


class TestCoreSkillScoring:
    def setup_method(self):
        self.svc = ScoringService()

    def test_full_match_scores_high(self):
        required = ["Python", "LangChain", "Azure OpenAI"]
        user     = {"languages": ["Python"], "frameworks": ["LangChain", "FastAPI"],
                    "cloud": ["Azure OpenAI", "AWS"]}
        score = self.svc._score_core_skills(required, user)
        assert score >= 80

    def test_no_match_scores_zero(self):
        required = ["COBOL", "Fortran", "Mainframe"]
        user     = {"languages": ["Python"], "frameworks": ["FastAPI"]}
        score = self.svc._score_core_skills(required, user)
        assert score == 0

    def test_partial_match_scores_proportionally(self):
        required = ["Python", "Java", "Go"]
        user     = {"languages": ["Python"]}
        score = self.svc._score_core_skills(required, user)
        assert 0 < score < 100

    def test_empty_required_skills(self):
        score = self.svc._score_core_skills([], {"languages": ["Python"]})
        assert score == 0

    def test_empty_user_skills(self):
        score = self.svc._score_core_skills(["Python"], {})
        assert score == 0

    def test_case_insensitive_matching(self):
        required = ["python", "LANGCHAIN"]
        user     = {"languages": ["Python"], "frameworks": ["LangChain"]}
        score = self.svc._score_core_skills(required, user)
        assert score > 0
