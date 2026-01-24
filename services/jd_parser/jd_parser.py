"""JD parsing service using LLM."""

from typing import Dict, Any, Optional
from openai import OpenAI
from packages.common.llm_cache import JDParseCache
from packages.common.logging import get_logger
from packages.schemas.jd_schema import ParsedJD
import json
import os
import hashlib

logger = get_logger(__name__)


class JDParser:
    """Parse job descriptions using LLM."""
    
    def __init__(self):
        """Initialize JD parser."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        self.client = OpenAI(api_key=api_key)
        self.cache = JDParseCache()
        self.model = "gpt-4"  # Use GPT-4 for structured output
    
    def _create_prompt(self, jd_text: str) -> str:
        """Create prompt for JD parsing."""
        return f"""Parse the following job description and extract structured information.

Job Description:
{jd_text[:4000]}

Return a JSON object with the following structure:
{{
    "role": "Job title/role",
    "seniority": "Intern|Junior|Mid|Senior|Staff|Principal|Unknown",
    "employment_type": "Full-time|Contract|Part-time|Unknown",
    "location_type": "Remote|Hybrid|Onsite|Unknown",
    "must_have_skills": ["skill1", "skill2", ...],
    "nice_to_have_skills": ["skill1", "skill2", ...],
    "responsibilities": ["responsibility1", "responsibility2", ...],
    "ats_keywords": ["keyword1", "keyword2", ...],
    "red_flags": ["flag1", "flag2", ...],
    "salary_range": {{
        "min": <number or null>,
        "max": <number or null>,
        "currency": "USD"
    }}
}}

Return only valid JSON, no additional text."""

    def parse(self, jd_text: str) -> ParsedJD:
        """Parse job description.
        
        Args:
            jd_text: Job description text
        
        Returns:
            Parsed JD object
        """
        # Generate content hash for caching
        content_hash = hashlib.sha256(jd_text.encode()).hexdigest()
        
        # Check cache first
        cached = self.cache.get(jd_text)
        if cached:
            logger.info(f"JD parse cache hit (hash: {content_hash[:8]}...)")
            return ParsedJD(**cached)
        
        # Call LLM
        try:
            prompt = self._create_prompt(jd_text)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at parsing job descriptions. Always return valid JSON matching the exact schema."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            # Validate with Pydantic
            parsed_jd = ParsedJD(**result)
            
            # Cache result
            self.cache.set(jd_text, parsed_jd.dict())
            
            logger.info(f"JD parsed successfully (hash: {content_hash[:8]}...)")
            return parsed_jd
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response was: {result_text[:500]}")
            # Try repair
            return self._repair_parse(jd_text, result_text, e)
        except Exception as e:
            logger.error(f"JD parsing failed: {e}")
            raise
    
    def _repair_parse(self, jd_text: str, invalid_json: str, error: Exception) -> ParsedJD:
        """Attempt to repair invalid JSON parse."""
        logger.warning("Attempting to repair invalid JSON parse")
        
        try:
            # Try to fix common JSON issues
            repair_prompt = f"""The following JSON parsing failed with error: {str(error)}

Invalid JSON:
{invalid_json[:1000]}

Please fix the JSON and return only valid JSON matching this schema:
{{
    "role": "string",
    "seniority": "Intern|Junior|Mid|Senior|Staff|Principal|Unknown",
    "employment_type": "Full-time|Contract|Part-time|Unknown",
    "location_type": "Remote|Hybrid|Onsite|Unknown",
    "must_have_skills": ["string"],
    "nice_to_have_skills": ["string"],
    "responsibilities": ["string"],
    "ats_keywords": ["string"],
    "red_flags": ["string"],
    "salary_range": {{"min": number|null, "max": number|null, "currency": "USD"}}
}}"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a JSON repair expert. Fix the JSON and return only valid JSON."},
                    {"role": "user", "content": repair_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            parsed_jd = ParsedJD(**result)
            
            # Cache repaired result
            self.cache.set(jd_text, parsed_jd.dict())
            
            logger.info("JD parse repaired successfully")
            return parsed_jd
            
        except Exception as repair_error:
            logger.error(f"Repair attempt failed: {repair_error}")
            # Return fallback with minimal data
            return ParsedJD(
                role="Unknown",
                seniority="Unknown",
                employment_type="Unknown",
                location_type="Unknown"
            )
