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

        Skills: Python, TypeScript, Machine Learning, Cloud Infrastructure
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
    """Regression: role_extractor.extract_roles must accept (resume_text: str, resume_hash: str).
    The original bug was calling it with (file_bytes, file_type) which caused a 500.
    """

    def test_extract_roles_accepts_str_not_bytes(self):
        extractor   = RoleExtractor()
        resume_text = "Senior GenAI Engineer with 6 years Python experience"
        resume_hash = "abc123"

        with patch.object(extractor, "_call_llm", return_value=["Senior GenAI Engineer"]):
            roles = extractor.extract_roles(resume_text, resume_hash)

        assert isinstance(roles, list)
        assert all(isinstance(r, str) for r in roles)

    def test_extract_roles_rejects_bytes_gracefully(self):
        """Passing bytes (the old bug) should raise TypeError, not a silent 500."""
        extractor = RoleExtractor()
        with pytest.raises((TypeError, AttributeError)):
            # Should fail at text processing, not deep inside Azure OpenAI call
            extractor.extract_roles(b"bytes content", "hash")  # bytes, not str
