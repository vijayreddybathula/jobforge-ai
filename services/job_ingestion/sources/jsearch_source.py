"""JSearch API job source - container native LinkedIn/Indeed job search."""

import os
import requests
from typing import List, Dict, Any, Optional
from packages.common.logging import get_logger

logger = get_logger(__name__)

JSEARCH_BASE_URL = "https://jsearch.p.rapidapi.com"


class JSearchAPIError(Exception):
    """Raised when the JSearch API returns an error response."""
    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class JSearchSource:
    """Fetch jobs from JSearch API (RapidAPI) - works from any container."""

    def __init__(self):
        self.api_key = os.getenv("JSEARCH_API_KEY")
        self.api_host = os.getenv("JSEARCH_API_HOST", "jsearch.p.rapidapi.com")

        if not self.api_key:
            raise ValueError("JSEARCH_API_KEY environment variable not set")

        self.headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host,
        }

    def test_connection(self) -> Dict[str, Any]:
        """Ping JSearch with a minimal query to verify API key and connectivity.

        Returns a dict with 'ok', 'status_code', and 'detail'.
        Does NOT ingest anything.
        """
        try:
            response = requests.get(
                f"{JSEARCH_BASE_URL}/search",
                headers=self.headers,
                params={"query": "software engineer", "page": 1, "num_pages": 1},
                timeout=10,
            )
            body_preview = response.text[:300]
            if response.status_code == 200:
                data = response.json()
                count = len(data.get("data", []))
                return {
                    "ok": True,
                    "status_code": 200,
                    "jobs_returned": count,
                    "detail": f"JSearch reachable — {count} jobs returned for test query",
                }
            else:
                return {
                    "ok": False,
                    "status_code": response.status_code,
                    "detail": f"JSearch returned {response.status_code}: {body_preview}",
                }
        except requests.exceptions.Timeout:
            return {"ok": False, "status_code": None, "detail": "JSearch API timed out"}
        except Exception as e:
            return {"ok": False, "status_code": None, "detail": str(e)}

    def search_jobs(
        self,
        keywords: str,
        location: str = "United States",
        work_type: Optional[str] = None,
        date_posted: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search jobs via JSearch API and return normalized job list.

        Raises JSearchAPIError on HTTP/network failures so callers can
        distinguish real API errors from genuinely empty result sets.

        Args:
            keywords: Job title / role keywords e.g. 'Senior GenAI Engineer'
            location: Location string e.g. 'Dallas, TX'
            work_type: Comma-separated work types: 'remote', 'hybrid', 'onsite'
            date_posted: Filter by posting date: 'today', '3days', 'week', 'month'
            max_results: Max number of jobs to return (10 per page)

        Returns:
            List of normalized job dicts ready for IngestionService.ingest_batch()
        """
        jobs: List[Dict[str, Any]] = []
        page = 1
        pages_needed = max(1, -(-max_results // 10))  # ceil division

        query = f"{keywords} in {location}" if location else keywords

        while len(jobs) < max_results and page <= pages_needed:
            params: Dict[str, Any] = {
                "query": query,
                "page": page,
                "num_pages": 1,
            }

            if date_posted:
                params["date_posted"] = date_posted

            if work_type:
                params["remote_jobs_only"] = "true" if "remote" in work_type.lower() else "false"

            try:
                response = requests.get(
                    f"{JSEARCH_BASE_URL}/search",
                    headers=self.headers,
                    params=params,
                    timeout=15,
                )
            except requests.exceptions.Timeout:
                raise JSearchAPIError("JSearch API timed out after 15s")
            except requests.exceptions.ConnectionError as e:
                raise JSearchAPIError(f"JSearch API connection failed: {e}")
            except Exception as e:
                raise JSearchAPIError(f"JSearch API request failed: {e}")

            if not response.ok:
                body_preview = response.text[:500]
                logger.error(
                    f"JSearch API HTTP {response.status_code} on page {page}: {body_preview}"
                )
                raise JSearchAPIError(
                    f"JSearch API returned HTTP {response.status_code}",
                    status_code=response.status_code,
                    body=body_preview,
                )

            try:
                data = response.json()
            except Exception as e:
                raise JSearchAPIError(f"JSearch API returned non-JSON response: {e}")

            raw_jobs = data.get("data", [])
            if not raw_jobs:
                logger.info(f"No more jobs returned at page {page}")
                break

            for raw in raw_jobs:
                if len(jobs) >= max_results:
                    break
                normalized = self._normalize(raw)
                if normalized:
                    jobs.append(normalized)

            page += 1

        logger.info(f"JSearch returned {len(jobs)} jobs for '{keywords}' in '{location}'")
        return jobs

    def _normalize(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize a raw JSearch job into the format expected by IngestionService."""
        try:
            title = raw.get("job_title", "").strip()
            company = raw.get("employer_name", "").strip()
            location_parts = [
                raw.get("job_city", ""),
                raw.get("job_state", ""),
                raw.get("job_country", ""),
            ]
            location = ", ".join(p for p in location_parts if p).strip()

            if raw.get("job_is_remote"):
                location = f"{location} (Remote)".strip(", ")

            description = raw.get("job_description", "").strip()
            source_url = raw.get("job_apply_link") or raw.get("job_url", "")
            posted_at = raw.get("job_posted_at_datetime_utc")

            if not title or not company or not description:
                logger.debug(f"Skipping incomplete job: {title} @ {company}")
                return None

            return {
                "url": source_url,
                "title": title,
                "company": company,
                "location": location,
                "description": description,
                "posted_at": posted_at,
                "employment_type": raw.get("job_employment_type", ""),
                "salary_min": raw.get("job_min_salary"),
                "salary_max": raw.get("job_max_salary"),
                "salary_currency": raw.get("job_salary_currency", "USD"),
                "salary_period": raw.get("job_salary_period", ""),
            }

        except Exception as e:
            logger.error(f"Failed to normalize job: {e}")
            return None
