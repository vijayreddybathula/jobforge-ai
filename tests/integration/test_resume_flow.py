"""Integration tests for resume analysis flow."""

import pytest
from services.resume_analyzer.resume_parser import ResumeParser
from services.resume_analyzer.role_extractor import RoleExtractor


def test_resume_parsing_flow():
    """Test complete resume parsing flow."""
    parser = ResumeParser()

    # Create sample resume content
    resume_text = """
    John Doe
    Senior Software Engineer
    
    Experience:
    - Built GenAI-powered systems using OpenAI API
    - Led team of 5 engineers
    - Technologies: Python, FastAPI, React, AWS
    
    Skills: Python, TypeScript, Machine Learning, Cloud Infrastructure
    """

    # Parse resume
    result = parser._parse_sections(resume_text)

    assert "experience" in result
    assert "skills" in result
    assert len(result["experience"]) > 0
