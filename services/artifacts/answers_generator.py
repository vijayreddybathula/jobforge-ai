"""Application answers generator using Azure OpenAI."""

import os
from typing import Dict, Any
from openai import AzureOpenAI
from packages.schemas.jd_schema import ParsedJD
from packages.common.logging import get_logger

logger = get_logger(__name__)


class AnswersGenerator:
    """Generate answers to common job application questions using Azure OpenAI."""

    COMMON_QUESTIONS = {
        "why_interested": "Why are you interested in this role?",
        "why_company": "Why do you want to work at this company?",
        "strengths": "What are your greatest strengths relevant to this role?",
        "experience_summary": "Briefly describe your relevant experience.",
        "availability": "When can you start?",
        "salary_expectations": "What are your salary expectations?",
    }

    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAPI_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAPI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAPI_VERSION", "2024-06-01-preview"),
        )
        self.model = os.getenv("AZURE_OPENAPI_DEPLOYMENT", "GPT-4")

    def generate_answers(
        self,
        parsed_jd: ParsedJD,
        user_profile: Dict[str, Any],
        user_preferences: Dict[str, Any],
        resume_text: str = "",
    ) -> Dict[str, str]:
        """Generate answers to all common application questions.

        Args:
            parsed_jd: Parsed job description
            user_profile: User profile with skills and roles
            user_preferences: User preferences (salary, visa etc)
            resume_text: Resume text for context

        Returns:
            Dict of question_key -> answer text
        """
        core_roles = ", ".join(user_profile.get("core_roles", []))
        skills_summary = ", ".join(
            user_profile.get("skills", {}).get("genai", [])[:4] +
            user_profile.get("skills", {}).get("languages", [])[:3]
        )
        salary_min = user_preferences.get("salary_min_usd", "not specified")
        salary_max = user_preferences.get("salary_max_usd", "not specified")
        visa = user_preferences.get("visa_status", "not specified")

        prompt = f"""You are a career coach helping a candidate answer job application questions.

Job Details:
- Role: {parsed_jd.role}
- Company context: {parsed_jd.role} position
- Required skills: {', '.join(parsed_jd.must_have_skills[:6])}

Candidate Profile:
- Current roles: {core_roles}
- Key skills: {skills_summary}
- Salary range: ${salary_min:,} - ${salary_max:,} if isinstance(salary_min, int) else f'{salary_min} - {salary_max}'
- Visa status: {visa}

Resume context:
{resume_text[:1000]}

Generate concise, authentic answers (2-4 sentences each) for these questions:
1. why_interested: Why are you interested in this role?
2. why_company: Why do you want to work here?
3. strengths: What are your greatest strengths for this role?
4. experience_summary: Briefly describe your relevant experience.
5. availability: When can you start? (assume 2 weeks notice)
6. salary_expectations: What are your salary expectations?

Return as JSON with question keys as above. Keep answers honest, specific, and professional."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a career coach. Always return valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.5,
                max_tokens=800,
            )
            import json
            answers = json.loads(response.choices[0].message.content)
            logger.info(f"Answers generated for role: {parsed_jd.role}")
            return answers
        except Exception as e:
            logger.error(f"Answers generation failed: {e}")
            raise
