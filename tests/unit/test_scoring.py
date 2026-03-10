"""Unit tests for scoring service.

Tests use the REAL scoring service implementation — thresholds and skill
scoring logic come from the actual code, not hardcoded expectations.
"""

import pytest
from unittest.mock import Mock
from services.scoring.scoring_service import ScoringService


class TestVerdictThresholds:
    """Ensure verdict bands stay correct.
    Thresholds must match _determine_verdict() in scoring_service.py.
    """

    def setup_method(self):
        self.svc = ScoringService()

    def test_skip_at_0(self):
        assert self.svc._determine_verdict(0) == "SKIP"

    def test_skip_at_49(self):
        assert self.svc._determine_verdict(49) == "SKIP"

    def test_validate_at_50(self):
        # 50 should NOT be SKIP
        assert self.svc._determine_verdict(50) != "SKIP"

    def test_auto_submit_at_100(self):
        # 100 should be the highest tier
        assert self.svc._determine_verdict(100) == "ELIGIBLE_AUTO_SUBMIT"

    def test_verdicts_are_monotone(self):
        """Higher scores must never give a lower verdict tier."""
        order = ["SKIP", "VALIDATE", "ASSISTED_APPLY", "ELIGIBLE_AUTO_SUBMIT"]
        prev_idx = 0
        for score in range(0, 101, 5):
            v   = self.svc._determine_verdict(score)
            idx = order.index(v)
            assert idx >= prev_idx, (
                f"Score {score} gave verdict {v} (tier {idx}) which is lower "
                f"than previous tier {prev_idx}"
            )
            prev_idx = idx


class TestCoreSkillScoring:
    def setup_method(self):
        self.svc = ScoringService()

    def test_perfect_match_scores_above_zero(self):
        """When all required skills are present, score must be > 0."""
        required = ["Python", "FastAPI", "PostgreSQL"]
        user     = {
            "languages":  ["Python"],
            "frameworks": ["FastAPI"],
            "data":       ["PostgreSQL"],
        }
        score = self.svc._score_core_skills(required, user)
        assert score > 0

    def test_no_user_skills_scores_zero(self):
        """User with no skills should score 0 regardless of requirements."""
        score = self.svc._score_core_skills(["Python", "Java"], {})
        assert score == 0

    def test_no_matching_skills_scores_zero(self):
        """User skills that don't match requirements score 0."""
        required = ["COBOL", "Fortran"]
        user     = {"languages": ["Python"], "frameworks": ["FastAPI"]}
        score = self.svc._score_core_skills(required, user)
        assert score == 0

    def test_partial_match_between_0_and_full(self):
        """Partial overlap scores between 0 and full-match score."""
        required  = ["Python", "Java", "Go"]
        user_full = {"languages": ["Python", "Java", "Go"]}
        user_half = {"languages": ["Python"]}
        score_full = self.svc._score_core_skills(required, user_full)
        score_half = self.svc._score_core_skills(required, user_half)
        assert 0 < score_half < score_full

    def test_empty_required_returns_non_negative(self):
        """Empty requirements: implementation defines the return; just must not crash."""
        score = self.svc._score_core_skills([], {"languages": ["Python"]})
        assert score >= 0

    def test_score_bounded_0_to_100(self):
        """Score must always be in [0, 100]."""
        for required, user in [
            (["Python"], {"languages": ["Python"]}),
            (["Python", "Java"], {"languages": ["Python"]}),
            (["COBOL"], {"languages": ["Python"]}),
            ([], {"languages": ["Python"]}),
            (["Python"], {}),
        ]:
            score = self.svc._score_core_skills(required, user)
            assert 0 <= score <= 100, f"Out of range ({score}) for {required} / {user}"
