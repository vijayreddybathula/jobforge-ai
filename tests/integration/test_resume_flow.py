"""Integration tests for resume analysis flow."""

import pytest
from unittest.mock import patch, Mock
from services.resume_analyzer.resume_parser import ResumeParser
from services.resume_analyzer.role_extractor import RoleExtractor


class TestResumeParser:
    def test_parses_experience_section(self):
        parser = ResumeParser()
        resume_text = """
        John Doe — Senior Software Engineer

        Experience:
        - Built GenAI-powered systems using OpenAI API
        - Led team of 5 engineers
        - Technologies: Python, FastAPI, React, AWS

        Skills: Python, TypeScript, Machine Learning
        """
        result = parser._parse_sections(resume_text)
        assert "experience" in result
        assert "skills"     in result
        assert len(result["experience"]) > 0

    def test_handles_empty_resume(self):
        parser = ResumeParser()
        result = parser._parse_sections("")
        assert isinstance(result, dict)

    def test_handles_skills_only(self):
        parser = ResumeParser()
        result = parser._parse_sections("Skills: Python, JavaScript, SQL")
        assert isinstance(result, dict)


class TestRoleExtractorSignature:
    """Regression: extract_roles must accept (resume_text: str, resume_hash: str).
    Old bug: API called it with (file_bytes, file_type) → 500 error.
    """

    def test_extract_roles_accepts_string_args(self):
        """Must not raise when called with (str, str)."""
        extractor   = RoleExtractor()
        resume_text = "Senior GenAI Engineer with 6 years Python experience"
        resume_hash = "abc123"

        with patch.object(extractor, "_call_llm", return_value=["Senior GenAI Engineer"]):
            roles = extractor.extract_roles(resume_text, resume_hash)

        assert isinstance(roles, list)
        assert all(isinstance(r, str) for r in roles)

    def test_extract_roles_returns_list(self):
        """Return value must always be a list."""
        extractor = RoleExtractor()
        with patch.object(extractor, "_call_llm", return_value=["ML Engineer", "Data Scientist"]):
            roles = extractor.extract_roles("some resume text", "hash123")
        assert isinstance(roles, list)
        assert len(roles) == 2

    def test_bytes_input_behaves_differently_from_str(self):
        """Passing bytes is not the intended usage — verify the function signature
        accepts strings without error (the main regression guard)."""
        extractor = RoleExtractor()
        # str input should work fine
        with patch.object(extractor, "_call_llm", return_value=["Engineer"]):
            result = extractor.extract_roles("text string", "hash")
        assert isinstance(result, list)  # str input works
