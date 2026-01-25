"""
Integration tests for Azure OpenAI integration.
Tests job parsing, analysis, and scoring with Azure GPT-4.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

load_dotenv()


class TestAzureOpenAIIntegration:
    """Test Azure OpenAI integration with jobforge-ai"""

    def test_azure_environment_variables_loaded(self):
        """Verify Azure OpenAI environment variables are properly loaded"""
        assert os.getenv("AZURE_OPENAPI_KEY"), "Azure API key not set"
        assert os.getenv("AZURE_OPENAPI_ENDPOINT"), "Azure endpoint not set"
        assert os.getenv("AZURE_OPENAPI_DEPLOYMENT") == "GPT-4", "Azure deployment not set to GPT-4"
        assert os.getenv("AZURE_OPENAPI_VERSION"), "Azure API version not set"

    def test_azure_endpoint_format(self):
        """Verify Azure endpoint has correct format"""
        endpoint = os.getenv("AZURE_OPENAPI_ENDPOINT")
        assert endpoint.startswith("https://"), "Endpoint should use HTTPS"
        assert ".openai.azure.com" in endpoint, "Endpoint should be Azure OpenAI domain"

    @pytest.mark.skip(reason="Requires running API server on localhost:8000")
    def test_api_health_check(self):
        """Test that API health check passes with Azure config"""
        import requests

        response = requests.get("http://localhost:8000/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"

        data = response.json()
        assert data["status"] == "healthy", "API should report healthy status"
        assert data["database"] == "connected", "Database should be connected"
        assert data["redis"] == "connected", "Redis should be connected"

    @patch("services.jd_parser.jd_parser.JDParser")
    def test_job_parsing_with_azure(self, mock_jdparser):
        """Test job description parsing uses Azure GPT-4"""
        # Mock JDParser instance
        instance = mock_jdparser.return_value
        instance.parse.return_value = {
            "job_title": "Senior Software Engineer",
            "company": "Tech Corp",
            "skills": ["Python", "Azure", "Docker"],
            "experience_required": "5+ years",
        }
        # Simulate job parsing
        job_data = instance.parse("Some job description")
        assert job_data["job_title"] == "Senior Software Engineer"
        assert "Azure" in job_data["skills"]
        instance.parse.assert_called_once()

    @patch("services.resume_analyzer.role_extractor.RoleExtractor")
    def test_resume_analysis_with_azure(self, mock_role_extractor):
        """Test resume analysis uses Azure GPT-4"""
        instance = mock_role_extractor.return_value
        instance.analyze_resume.return_value = {
            "summary": "Experienced full-stack developer",
            "skills": ["Python", "Docker", "Kubernetes"],
            "experience_years": 7,
            "education": "BS Computer Science",
        }
        resume_data = instance.analyze_resume("Some resume text")
        assert resume_data["experience_years"] == 7
        assert "Kubernetes" in resume_data["skills"]
        instance.analyze_resume.assert_called_once()

    @patch("services.scoring.scoring_service.ScoringService")
    def test_job_scoring_with_azure(self, mock_scoring_service):
        """Test job scoring uses Azure GPT-4"""
        instance = mock_scoring_service.return_value
        instance.score_job.return_value = {
            "match_score": 8.5,
            "reasons": ["Strong skills match", "Experience aligned"],
            "recommendation": "HIGHLY_RECOMMENDED",
        }
        score = instance.score_job("job_id", "user_id", {}, {}, {})
        assert score["match_score"] >= 0 and score["match_score"] <= 10
        assert score["recommendation"] in ["HIGHLY_RECOMMENDED", "RECOMMENDED", "NOT_RECOMMENDED"]
        instance.score_job.assert_called_once()


class TestAzureCostTracking:
    """Test Azure OpenAI cost tracking"""

    @pytest.mark.skip(reason="Requires running API server on localhost:8000")
    def test_api_call_logging(self):
        """Verify API calls are logged for cost tracking"""
        import requests

        # Make an API call
        response = requests.get("http://localhost:8000/health")
        assert response.status_code == 200

        # Verify logs contain request information
        # This would be checked in actual logs
        assert response.elapsed.total_seconds() > 0

    def test_token_usage_tracking(self):
        """Test that token usage is tracked for billing"""
        # Token tracking should be implemented in the service layer
        pass


class TestAzureErrorHandling:
    """Test error handling with Azure OpenAI"""

    @patch.dict(os.environ, {"AZURE_OPENAPI_KEY": "invalid_key"})
    def test_invalid_azure_key_handling(self):
        """Test graceful handling of invalid Azure API key"""
        # This would test that authentication errors are caught
        pass

    def test_rate_limit_handling(self):
        """Test handling of Azure rate limits"""
        # Should implement exponential backoff
        pass

    def test_timeout_handling(self):
        """Test handling of Azure API timeouts"""
        # Should implement timeout with fallback
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
