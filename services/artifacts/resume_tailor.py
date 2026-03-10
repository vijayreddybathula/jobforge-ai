"""
Resume tailoring service using Azure OpenAI.
Guardrail: LLM may only SELECT and REPHRASE from the approved bullet library.
It cannot invent new claims, metrics, employers, or tools.
"""

import os
import json
from typing import Dict, Any, List
from openai import AzureOpenAI
from packages.schemas.jd_schema import ParsedJD
from packages.bullet_library import get_bullets_by_tags, get_all_bullets
from packages.common.logging import get_logger

logger = get_logger(__name__)


class ResumeTailor:
    """Tailor resume bullets to a specific job — guardrailed by approved bullet library."""

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
        """
        Generate tailored resume output using ONLY approved bullets from the library.
        LLM selects the most relevant bullets and may rephrase to incorporate ATS keywords,
        but cannot invent new facts, tools, employers, or metrics.

        Returns:
            summary: tailored professional summary
            bullets: list of selected+tailored bullet strings
            bullet_ids_used: IDs from the library (audit trail)
            keywords_incorporated: ATS keywords woven in
        """
        must_haves = ", ".join(parsed_jd.must_have_skills[:8])
        ats_keywords = ", ".join(parsed_jd.ats_keywords[:12])

        # Retrieve most relevant bullets from library based on JD skills
        all_jd_terms = parsed_jd.must_have_skills + parsed_jd.nice_to_have_skills + parsed_jd.ats_keywords
        relevant_bullets = get_bullets_by_tags(all_jd_terms)

        # If few matches, fall back to all bullets
        if len(relevant_bullets) < 5:
            relevant_bullets = get_all_bullets()

        # Build bullet library prompt context
        bullet_library_text = "\n".join(
            f"[{b['id']}] {b['text']}" for b in relevant_bullets[:14]
        )

        prompt = f"""You are an expert resume writer. Your job is to select and tailor resume bullets for a specific job.

CRITICAL GUARDRAIL: You may ONLY use bullets from the approved library below.
You may rephrase bullets to incorporate ATS keywords, but you CANNOT:
- Invent new tools, technologies, or employers
- Add metrics or numbers not present in the original bullet
- Claim experience the candidate does not have
- Combine bullets in a way that creates false claims

=== APPROVED BULLET LIBRARY ===
{bullet_library_text}

=== JOB REQUIREMENTS ===
Role: {parsed_jd.role}
Seniority: {parsed_jd.seniority}
Must-have skills: {must_haves}
ATS keywords to weave in: {ats_keywords}

=== TASK ===
1. Select the 5-7 most relevant bullets from the library above
2. Rephrase each selected bullet to naturally incorporate the ATS keywords where truthful
3. Write a 2-3 sentence tailored professional summary
4. Return the exact bullet IDs you selected

Return JSON:
{{
  "summary": "tailored professional summary",
  "bullets": ["tailored bullet 1", "tailored bullet 2", ...],
  "bullet_ids_used": ["VR-001", "VR-005", ...],
  "keywords_incorporated": ["keyword1", "keyword2", ...]
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert resume writer. ONLY use bullets from the provided library. Return valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1200,
            )
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Resume tailored for role: {parsed_jd.role} | bullets used: {result.get('bullet_ids_used', [])}")
            return result
        except Exception as e:
            logger.error(f"Resume tailoring failed: {e}")
            raise
