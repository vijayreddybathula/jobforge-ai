"""Recruiter pitch generator using Azure OpenAI."""

import os
import json
from typing import Dict, Any
from openai import AzureOpenAI
from packages.schemas.jd_schema import ParsedJD
from packages.common.logging import get_logger

logger = get_logger(__name__)


class PitchGenerator:
    """Generate a recruiter pitch using Azure OpenAI."""

    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAPI_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAPI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAPI_VERSION", "2024-06-01-preview"),
        )
        self.model = os.getenv("AZURE_OPENAPI_DEPLOYMENT", "GPT-4")

    def generate(
        self,
        parsed_jd: ParsedJD,
        user_profile: Dict[str, Any],
        resume_text: str = "",
        score: int = 75,
    ) -> str:
        """Generate a personalized recruiter pitch.

        Args:
            parsed_jd: Parsed job description
            user_profile: User profile with skills and roles
            resume_text: Raw resume text for context
            score: Fit score (0-100)

        Returns:
            Pitch text (3-5 sentences, ready to paste into applications)
        """
        skills_summary = ", ".join(
            user_profile.get("skills", {}).get("genai", [])[:5] +
            user_profile.get("skills", {}).get("languages", [])[:3]
        )
        core_roles = ", ".join(user_profile.get("core_roles", []))
        must_haves = ", ".join(parsed_jd.must_have_skills[:6])

        prompt = f"""You are a professional career coach. Write a concise, compelling recruiter pitch (3-5 sentences) for a job application.

Job Role: {parsed_jd.role}
Seniority: {parsed_jd.seniority}
Must-have skills required: {must_haves}

Candidate profile:
- Current roles: {core_roles}
- Key skills: {skills_summary}
- Fit score: {score}/100

Resume snippet:
{resume_text[:800]}

Write a pitch that:
1. Opens with the candidate's most relevant experience
2. Highlights 2-3 specific skill matches to the job
3. Closes with enthusiasm and a call to action
4. Sounds human and natural, NOT like an AI template
5. Is 3-5 sentences maximum

Return only the pitch text, no labels or formatting."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert career coach who writes compelling, personalized job application pitches."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=300,
            )
            pitch = response.choices[0].message.content.strip()
            logger.info(f"Pitch generated for role: {parsed_jd.role}")
            return pitch
        except Exception as e:
            logger.error(f"Pitch generation failed: {e}")
            raise
