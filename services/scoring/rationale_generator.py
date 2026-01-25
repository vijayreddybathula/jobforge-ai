"""LLM-based rationale generator for scoring."""

from typing import Dict, Any
from openai import OpenAI
from packages.common.llm_cache import LLMCache
from packages.common.logging import get_logger
from packages.schemas.jd_schema import ParsedJD
import json
import os

logger = get_logger(__name__)


class RationaleGenerator:
    """Generate human-readable rationale for scores using LLM."""

    def __init__(self):
        """Initialize rationale generator."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(api_key=api_key)
        self.cache = LLMCache(ttl=604800)  # 7 days
        self.model = "gpt-3.5-turbo"  # Use cheaper model for rationale

    def generate(
        self,
        score: int,
        breakdown: Dict[str, int],
        parsed_jd: ParsedJD,
        user_skills: Dict[str, Any],
    ) -> str:
        """Generate rationale for score.

        Args:
            score: Total fit score
            breakdown: Score breakdown by category
            parsed_jd: Parsed job description
            user_skills: User skills

        Returns:
            Human-readable rationale
        """
        # Create cache key
        cache_key = f"{parsed_jd.role}:{score}:{json.dumps(breakdown, sort_keys=True)}"

        # Check cache
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        # Generate prompt
        prompt = f"""Explain why this job has a fit score of {score}/100.

Score breakdown:
- Core skill match: {breakdown.get('core_skill_match', 0)}/100
- Nice-to-have skills: {breakdown.get('nice_to_have_skills', 0)}/100
- Seniority alignment: {breakdown.get('seniority_alignment', 0)}/100
- Domain/industry: {breakdown.get('domain_industry', 0)}/100
- Location fit: {breakdown.get('location_fit', 0)}/100
- Compensation: {breakdown.get('compensation', 0)}/100

Job: {parsed_jd.role}
Required skills: {', '.join(parsed_jd.must_have_skills[:10])}
User skills: {', '.join(user_skills.get('languages', [])[:5])}

Provide a concise 2-3 sentence explanation highlighting strengths and gaps."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at explaining job fit scores. Be concise and helpful.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=150,
            )

            rationale = response.choices[0].message.content.strip()

            # Cache result
            self.cache.set(cache_key, rationale)

            return rationale

        except Exception as e:
            logger.error(f"Rationale generation failed: {e}")
            # Return fallback
            return f"Fit score: {score}/100. Review job details for specific match factors."
