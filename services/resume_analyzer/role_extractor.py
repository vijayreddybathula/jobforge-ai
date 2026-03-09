"""Role extraction service using LLM."""

import hashlib
import io
import json
import os
from typing import Any, Dict, List, Optional

from openai import AzureOpenAI

from packages.common.llm_cache import ResumeAnalysisCache
from packages.common.logging import get_logger
from packages.schemas.resume import ResumeAnalysisResponse
from packages.schemas.resume import RoleMatch as RoleMatchSchema

logger = get_logger(__name__)


def _extract_text(file_bytes: bytes, file_type: str) -> str:
    """
    Extract plain text from PDF or DOCX bytes.
    Falls back to raw UTF-8 decode if neither library is available.
    """
    ft = file_type.lower().strip(".")

    if ft == "pdf":
        try:
            import pypdf  # pypdf >= 3.x
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            return "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        except ImportError:
            pass
        try:
            import pdfminer.high_level as pdfminer
            return pdfminer.extract_text(io.BytesIO(file_bytes))
        except ImportError:
            pass

    elif ft in ("docx", "doc"):
        try:
            import docx2txt
            # docx2txt.process() accepts a file-like object
            return docx2txt.process(io.BytesIO(file_bytes))
        except ImportError:
            pass
        try:
            from docx import Document
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            pass

    # Last resort: try to decode as UTF-8 text (works for plain-.txt uploads)
    try:
        return file_bytes.decode("utf-8", errors="replace")
    except Exception:
        return ""


class RoleExtractor:
    """Extract role information from a resume using an LLM."""

    def __init__(self):
        api_key    = os.getenv("AZURE_OPENAPI_KEY")
        endpoint   = os.getenv("AZURE_OPENAPI_ENDPOINT")
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

    # ------------------------------------------------------------------ #
    #  Public API called by resume.py                                      #
    # ------------------------------------------------------------------ #

    def extract_roles(self, file_bytes: bytes, file_type: str) -> List[Dict[str, Any]]:
        """
        Extract suggested roles from raw resume bytes.

        Args:
            file_bytes: Raw file content (PDF or DOCX).
            file_type:  'pdf' | 'docx' | 'doc'

        Returns:
            List of dicts with keys: role, confidence, reasoning
        """
        resume_text = _extract_text(file_bytes, file_type)
        if not resume_text.strip():
            logger.warning("Text extraction yielded empty result — returning empty roles")
            return []

        content_hash = hashlib.sha256(file_bytes).hexdigest()
        cache_key    = f"roles:{content_hash}"

        cached = self.cache.get(cache_key)
        if cached:
            logger.info("extract_roles cache hit")
            return cached

        raw = self._call_llm(resume_text)

        # Normalise to the shape resume.py expects: [{role, confidence, reasoning}]
        roles: List[Dict[str, Any]] = []
        for item in raw.get("suggested_roles", []):
            roles.append({
                "role":       item.get("role_title") or item.get("role", ""),
                "confidence": item.get("confidence_score") or item.get("confidence", 70),
                "reasoning":  item.get("reasoning", ""),
            })

        self.cache.set(cache_key, roles)
        logger.info(f"extract_roles: {len(roles)} roles for hash {content_hash[:8]}")
        return roles

    def analyze_resume(
        self, file_bytes: bytes, file_type: str
    ) -> ResumeAnalysisResponse:
        """
        Full analysis returning a structured ResumeAnalysisResponse.
        """
        resume_text  = _extract_text(file_bytes, file_type)
        content_hash = hashlib.sha256(file_bytes).hexdigest()
        cache_key    = f"analysis:{content_hash}"

        cached = self.cache.get(cache_key)
        raw    = cached if cached else self._call_llm(resume_text)
        if not cached:
            self.cache.set(cache_key, raw)

        suggested_roles = [
            RoleMatchSchema(
                role_title=r.get("role_title", ""),
                confidence_score=r.get("confidence_score", 0),
                reasoning=r.get("reasoning"),
            )
            for r in raw.get("suggested_roles", [])
        ]

        return ResumeAnalysisResponse(
            resume_id=None,
            current_role=raw.get("current_role"),
            years_of_experience=raw.get("years_of_experience"),
            core_skills=raw.get("core_skills", []),
            technologies=raw.get("technologies", []),
            industry_domain=raw.get("industry_domain"),
            seniority_level=raw.get("seniority_level"),
            suggested_roles=suggested_roles,
            parsed_sections={},
        )

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _call_llm(self, resume_text: str) -> Dict[str, Any]:
        """Call Azure OpenAI and return parsed JSON dict."""
        prompt = self._create_prompt(resume_text)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert at analysing resumes. "
                            "Always return valid JSON."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError as e:
            logger.error(f"LLM response parse error: {e}")
            return {"suggested_roles": []}
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _create_prompt(self, resume_text: str) -> str:
        return f"""Analyze the following resume and extract structured information.

Resume text:
{resume_text[:4000]}

Return a JSON object with this exact structure:
{{
    "current_role": "Current or most recent job title",
    "years_of_experience": <integer>,
    "core_skills": ["skill1", "skill2"],
    "technologies": ["tech1", "tech2"],
    "industry_domain": "Industry (e.g. Software, Finance)",
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
