"""JSearch API job source."""

import os
import requests
from typing import List, Dict, Any, Optional
from packages.common.logging import get_logger

logger = get_logger(__name__)

JSEARCH_BASE_URL = "https://jsearch.p.rapidapi.com"

# Default freshness window — only ingest jobs posted in the last week.
DEFAULT_DATE_POSTED = "week"


class JSearchAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class JSearchSource:
    """Fetch jobs from JSearch API (RapidAPI)."""

    def __init__(self):
        self.api_key  = os.getenv("JSEARCH_API_KEY")
        self.api_host = os.getenv("JSEARCH_API_HOST", "jsearch.p.rapidapi.com")
        if not self.api_key:
            raise ValueError("JSEARCH_API_KEY environment variable not set")
        self.headers = {
            "X-RapidAPI-Key":  self.api_key,
            "X-RapidAPI-Host": self.api_host,
        }

    def test_connection(self) -> Dict[str, Any]:
        try:
            response = requests.get(
                f"{JSEARCH_BASE_URL}/search",
                headers=self.headers,
                params={"query": "software engineer", "page": 1, "num_pages": 1},
                timeout=10,
            )
            if response.status_code == 200:
                count = len(response.json().get("data", []))
                return {"ok": True, "status_code": 200, "jobs_returned": count,
                        "detail": f"JSearch reachable — {count} jobs returned"}
            return {"ok": False, "status_code": response.status_code,
                    "detail": f"JSearch returned {response.status_code}: {response.text[:300]}"}
        except requests.exceptions.Timeout:
            return {"ok": False, "status_code": None, "detail": "JSearch API timed out"}
        except Exception as e:
            return {"ok": False, "status_code": None, "detail": str(e)}

    def search_jobs(
        self,
        keywords: str,
        location: str = "United States",
        work_type: Optional[str] = None,
        date_posted: Optional[str] = DEFAULT_DATE_POSTED,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search jobs via JSearch and return normalized list.

        date_posted defaults to 'week' to avoid returning already-closed
        listings.  Pass date_posted=None explicitly to remove the filter.

        Each returned dict contains BOTH:
          url        — JSearch canonical URL  (used as dedup key / source_url)
          apply_link — Direct ATS/employer apply link (what we open for the user)
        """
        jobs: List[Dict[str, Any]] = []
        page = 1
        pages_needed = max(1, -(-max_results // 10))  # ceil

        query = f"{keywords} in {location}" if location else keywords

        while len(jobs) < max_results and page <= pages_needed:
            params: Dict[str, Any] = {"query": query, "page": page, "num_pages": 1}

            if date_posted:
                params["date_posted"] = date_posted

            if work_type:
                if work_type.lower() == "remote":
                    params["remote_jobs_only"] = "true"
                elif "remote" not in work_type.lower():
                    params["remote_jobs_only"] = "false"

            try:
                response = requests.get(
                    f"{JSEARCH_BASE_URL}/search",
                    headers=self.headers, params=params, timeout=15,
                )
            except requests.exceptions.Timeout:
                raise JSearchAPIError("JSearch API timed out after 15s")
            except requests.exceptions.ConnectionError as e:
                raise JSearchAPIError(f"JSearch API connection failed: {e}")
            except Exception as e:
                raise JSearchAPIError(f"JSearch API request failed: {e}")

            if not response.ok:
                raise JSearchAPIError(
                    f"JSearch API returned HTTP {response.status_code}",
                    status_code=response.status_code,
                    body=response.text[:500],
                )

            try:
                data = response.json()
            except Exception as e:
                raise JSearchAPIError(f"JSearch API returned non-JSON response: {e}")

            raw_jobs = data.get("data", [])
            if not raw_jobs:
                break

            for raw in raw_jobs:
                if len(jobs) >= max_results:
                    break
                normalized = self._normalize(raw)
                if normalized:
                    jobs.append(normalized)
            page += 1

        logger.info(f"JSearch returned {len(jobs)} jobs for '{keywords}' in '{location}' (date_posted={date_posted})")
        return jobs

    def _normalize(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normalize a raw JSearch job.

        CRITICAL: job_url must be non-empty — it is stored as source_url which
        has a UNIQUE constraint in the DB.  If two jobs have empty job_url they
        both resolve to "" and the second INSERT violates the constraint, causing
        a silent rollback that swallows the entire batch without error counts.
        Jobs with no job_url are skipped here.

        url        = job_url  — JSearch canonical URL, stable dedup key.
        apply_link = job_apply_link — Actual employer/ATS link shown to user.
        """
        try:
            title   = raw.get("job_title", "").strip()
            company = raw.get("employer_name", "").strip()
            loc_parts = [
                raw.get("job_city", ""),
                raw.get("job_state", ""),
                raw.get("job_country", ""),
            ]
            location = ", ".join(p for p in loc_parts if p).strip()
            if raw.get("job_is_remote"):
                location = f"{location} (Remote)".strip(", ")

            description = raw.get("job_description", "").strip()

            # job_url is the canonical JSearch URL — must be non-empty.
            job_url = raw.get("job_url", "").strip()

            # Skip jobs with no canonical URL — they cannot be safely deduped
            # and will break the unique constraint on source_url.
            if not job_url:
                logger.warning(f"Skipping job with empty job_url: '{title}' @ '{company}'")
                return None

            apply_link = (raw.get("job_apply_link") or job_url).strip()
            posted_at  = raw.get("job_posted_at_datetime_utc")

            if not title or not company or not description:
                logger.debug(f"Skipping incomplete job: title={bool(title)} company={bool(company)} desc={bool(description)}")
                return None

            return {
                "url":             job_url,
                "apply_link":      apply_link,
                "title":           title,
                "company":         company,
                "location":        location,
                "description":     description,
                "posted_at":       posted_at,
                "employment_type": raw.get("job_employment_type", ""),
                "salary_min":      raw.get("job_min_salary"),
                "salary_max":      raw.get("job_max_salary"),
                "salary_currency": raw.get("job_salary_currency", "USD"),
                "salary_period":   raw.get("job_salary_period", ""),
            }
        except Exception as e:
            logger.error(f"Failed to normalize job: {e}")
            return None
