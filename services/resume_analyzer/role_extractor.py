"""Role extraction service using LLM."""

from typing import List, Dict, Any, Optional
from openai import AzureOpenAI
from packages.common.llm_cache import ResumeAnalysisCache
from packages.common.logging import get_logger
from packages.schemas.resume import RoleMatch, ResumeAnalysisResponse
import json
import os
import hashlib

logger = get_logger(__name__)


class RoleExtractor:
    """Extract role information from resume using LLM."""

    def __init__(self):
        """Initialize role extractor."""
        api_key = os.getenv("AZURE_OPENAPI_KEY")
        endpoint = os.getenv("AZURE_OPENAPI_ENDPOINT")
        api_version = os.getenv("AZURE_OPENAPI_VERSION", "2024-06-01-preview")

        if not api_key:
            raise ValueError("AZURE_OPENAPI_KEY environment variable not set")
        if not endpoint:
            raise ValueError("AZURE_OPENAPI_ENDPOINT environment variable not set")

        self.client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )
        self.cache = ResumeAnalysisCache()
        self.model = os.getenv("AZURE_OPENAPI_DEPLOYMENT", "GPT-4")

    def _create_prompt(self, resume_text: str) -> str:
        """Create prompt for role extraction."""
        return f"""Analyze the following resume and extract structured information.

Resume text:
{resume_text[:4000]}

Please extract and return a JSON object with the following structure:
{{
    "current_role": "Current job title or most recent role",
    "years_of_experience": <number>,
    "core_skills": ["skill1", "skill2", ...],
    "technologies": ["tech1", "tech2", ...],
    "industry_domain": "Industry or domain (e.g., Software, Finance, Healthcare)",
    "seniority_level": "Intern|Junior|Mid|Senior|Staff|Principal|Unknown",
    "suggested_roles": [
        {{
            "role_title": "Suggested role title",
            "confidence_score": <0-100>,
            "reasoning": "Why this role matches"
        }}
    ]
}}

Return only valid JSON, no additional text."""

    def extract_roles(self, resume_text: str, resume_hash: str) -> Dict[str, Any]:
        """Extract role information from resume.

        Args:
            resume_text: Resume text content
            resume_hash: Resume content hash for caching

        Returns:
            Extracted role information
        """
        # Check cache first
        cache_key = f"{resume_hash}:{hashlib.sha256(resume_text.encode()).hexdigest()}"
        cached = self.cache.get(cache_key)
        if cached:
            logger.info("Resume analysis cache hit")
            return cached

        # Call LLM
        try:
            prompt = self._create_prompt(resume_text)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing resumes and extracting role information. Always return valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            result_text = response.choices[0].message.content
            result = json.loads(result_text)

            # Cache result
            self.cache.set(cache_key, result)

            logger.info(f"Resume analysis completed for hash {resume_hash[:8]}...")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return {
                "current_role": None,
                "years_of_experience": None,
                "core_skills": [],
                "technologies": [],
                "industry_domain": None,
                "seniority_level": "Unknown",
                "suggested_roles": [],
            }
        except Exception as e:
            logger.error(f"Role extraction failed: {e}")
            raise

    def analyze_resume(self, resume_text: str, resume_hash: str) -> ResumeAnalysisResponse:
        """Analyze resume and return structured response.

        Args:
            resume_text: Resume text content
            resume_hash: Resume content hash

        Returns:
            Resume analysis response
        """
        extracted = self.extract_roles(resume_text, resume_hash)

        suggested_roles = [
            RoleMatch(
                role_title=role.get("role_title", ""),
                confidence_score=role.get("confidence_score", 0),
                reasoning=role.get("reasoning"),
            )
            for role in extracted.get("suggested_roles", [])
        ]

        return ResumeAnalysisResponse(
            resume_id=None,  # Will be set by caller
            current_role=extracted.get("current_role"),
            years_of_experience=extracted.get("years_of_experience"),
            core_skills=extracted.get("core_skills", []),
            technologies=extracted.get("technologies", []),
            industry_domain=extracted.get("industry_domain"),
            seniority_level=extracted.get("seniority_level"),
            suggested_roles=suggested_roles,
            parsed_sections={},
        )
