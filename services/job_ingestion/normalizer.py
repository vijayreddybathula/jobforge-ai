"""Job description normalizer and deduplicator."""

import hashlib
import re
from typing import Dict, Any
from packages.common.logging import get_logger

logger = get_logger(__name__)


class JobNormalizer:
    """Normalize job postings for deduplication."""

    def normalize(
        self, title: str, company: str, location: str, description: str
    ) -> Dict[str, Any]:
        """Normalize job posting data.

        Args:
            title: Job title
            company: Company name
            location: Job location
            description: Job description

        Returns:
            Normalized data with content hash
        """
        # Normalize title
        normalized_title = self._normalize_text(title)

        # Normalize company name
        normalized_company = self._normalize_company(company)

        # Normalize location
        normalized_location = self._normalize_location(location)

        # Normalize description (remove extra whitespace, normalize case)
        normalized_description = self._normalize_text(description)

        # Generate content hash
        content_for_hash = (
            f"{normalized_title}|{normalized_company}|{normalized_description[:1000]}"
        )
        content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()

        return {
            "title": normalized_title,
            "company": normalized_company,
            "location": normalized_location,
            "description": normalized_description,
            "content_hash": content_hash,
        }

    def _normalize_text(self, text: str) -> str:
        """Normalize text: lowercase, remove extra whitespace."""
        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)

        # Strip
        text = text.strip()

        return text

    def _normalize_company(self, company: str) -> str:
        """Normalize company name."""
        if not company:
            return ""

        # Remove common suffixes
        company = re.sub(
            r"\s+(inc|llc|corp|corporation|ltd|limited)\.?$", "", company, flags=re.IGNORECASE
        )

        # Normalize text
        company = self._normalize_text(company)

        return company

    def _normalize_location(self, location: str) -> str:
        """Normalize location string."""
        if not location:
            return ""

        # Remove common prefixes
        location = re.sub(r"^(remote|hybrid|onsite|on-site):\s*", "", location, flags=re.IGNORECASE)

        # Normalize text
        location = self._normalize_text(location)

        return location
