"""Resume tailoring service using Azure OpenAI."""

import os
from typing import Dict, Any, List
from openai import AzureOpenAI
from packages.schemas.jd_schema import ParsedJD
from packages.common.logging import get_logger

logger = get_logger(__name__)


class ResumeTailor:
    """Tailor resume bullets to a specific job using Azure OpenAI."""

    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAPI_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAPI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAPI_VERSION", "2024-06-01-preview"),
        )
        self.model = os.getenv("AZURE_OPENAPI_DEPLOYMENT", "GPT-4")

    def tailor_resume(
        self,
        resume_text: str,
        parsed_jd: ParsedJD,
        user_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate tailored resume bullets for a specific job.

        Args:
            resume_text: Full resume text content
            parsed_jd: Parsed job description
            user_profile: User profile with skills and roles

        Returns:
            Dict with tailored_bullets, keywords_added, summary
        """
        must_haves = ", ".join(parsed_jd.must_have_skills[:8])
        nice_to_haves = ", ".join(parsed_jd.nice_to_have_skills[:5])
        ats_keywords = ", ".join(parsed_jd.ats_keywords[:10])

        prompt = f"""You are an expert resume writer and ATS optimization specialist.

Job to tailor for:
- Role: {parsed_jd.role}
- Seniority: {parsed_jd.seniority}
- Must-have skills: {must_haves}
- Nice-to-have skills: {nice_to_haves}
- ATS keywords to include: {ats_keywords}

Candidate's current resume:
{resume_text[:3000]}

Task: Generate 5-7 tailored, ATS-optimized resume bullet points that:
1. Use STAR format (Situation/Task, Action, Result) where possible
2. Naturally incorporate the ATS keywords above
3. Quantify impact with metrics where possible
4. Highlight the most relevant experience for THIS specific role
5. Start each bullet with a strong action verb

Also provide:
- A 2-3 sentence tailored professional summary for this role
- List of ATS keywords successfully incorporated

Return as JSON with this structure:
{{
  "summary": "tailored professional summary here",
  "bullets": ["bullet 1", "bullet 2", ...],
  "keywords_incorporated": ["keyword1", "keyword2", ...]
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert resume writer. Always return valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.4,
                max_tokens=1000,
            )
            import json
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Resume tailored for role: {parsed_jd.role}")
            return result
        except Exception as e:
            logger.error(f"Resume tailoring failed: {e}")
            raise
