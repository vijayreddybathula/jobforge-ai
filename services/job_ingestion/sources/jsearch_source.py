"""JSearch API job source."""

import os
import requests
from typing import List, Dict, Any, Optional
from packages.common.logging import get_logger

logger = get_logger(__name__)

JSEARCH_BASE_URL = "https://jsearch.p.rapidapi.com"

# Default freshness window.
DEFAULT_DATE_POSTED = "week"

# Keyword aliases: if the user's role title contains these tokens, broaden the
# JSearch query to a term that actually returns results.  JSearch is a Google
# Jobs scraper — very niche compound terms like "GenAI Engineer" return 0 hits
# even though "AI Engineer" or "Machine Learning Engineer" return hundreds.
KEYWORD_ALIASES = {
    "genai":              "Generative AI Engineer",
    "gen ai":             "Generative AI Engineer",
    "generative ai":      "Generative AI Engineer",
    "llm":                "LLM Engineer",
    "mlops":              "MLOps Engineer",
    "aiops":              "AI Engineer",
    "nlp":                "NLP Engineer",
}


def _expand_keywords(keywords: str) -> str:
    """
    Map niche/compound role titles to JSearch-friendly equivalents.

    JSearch searches Google Jobs.  Very niche compound terms like
    'GenAI Engineer' return 0 results because no employer uses that exact
    string in their posting title.  We map them to broader equivalents that
    still represent the same role.

    Examples:
      'Senior GenAI Engineer'  -> 'Senior Generative AI Engineer'
      'GenAI'                  -> 'Generative AI Engineer'
      'LLM Engineer'           -> 'LLM Engineer'  (already good)
      'Python Developer'       -> 'Python Developer'  (unchanged)
    """
    kw_lower = keywords.lower()
    for token, replacement in KEYWORD_ALIASES.items():
        if token in kw_lower:
            # Preserve seniority prefix (Senior / Lead / Principal / Staff)
            seniority = ""
            for prefix in ("principal ", "staff ", "senior ", "lead ", "jr ", "junior "):
                if kw_lower.startswith(prefix):
                    seniority = keywords[:len(prefix)]
                    break
            expanded = f"{seniority}{replacement}".strip()
            logger.info(f"Keyword expanded: '{keywords}' -> '{expanded}'")
            return expanded
    return keywords


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

    def raw_search(self, keywords: str, location: str, date_posted: Optional[str] = None, num_results: int = 5) -> Dict[str, Any]:
        """Debug: return the raw JSearch API response without normalizing or ingesting."""
        expanded = _expand_keywords(keywords)
        query    = f"{expanded} in {location}" if location else expanded
        params: Dict[str, Any] = {"query": query, "page": 1, "num_pages": 1}
        if date_posted:
            params["date_posted"] = date_posted
        try:
            r = requests.get(f"{JSEARCH_BASE_URL}/search", headers=self.headers, params=params, timeout=15)
            data = r.json()
            jobs = data.get("data", [])[:num_results]
            return {
                "query_sent": query,
                "params": params,
                "http_status": r.status_code,
                "total_returned": len(data.get("data", [])),
                "sample": [
                    {
                        "title":       j.get("job_title"),
                        "company":     j.get("employer_name"),
                        "location":    f"{j.get('job_city','')} {j.get('job_state','')} {j.get('job_country','')}".strip(),
                        "job_url":     j.get("job_url", "")[:80],
                        "has_job_url": bool(j.get("job_url", "").strip()),
                        "posted_at":   j.get("job_posted_at_datetime_utc"),
                    }
                    for j in jobs
                ],
            }
        except Exception as e:
            return {"error": str(e)}

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

        Keywords are expanded via KEYWORD_ALIASES before sending to JSearch
        so niche terms like 'GenAI Engineer' are mapped to broader equivalents
        that Google Jobs (underlying JSearch) actually indexes.
        """
        # Expand keywords to JSearch-friendly terms
        expanded_keywords = _expand_keywords(keywords)
        if expanded_keywords != keywords:
            logger.info(f"Search: '{keywords}' expanded to '{expanded_keywords}'")

        jobs: List[Dict[str, Any]] = []
        page = 1
        pages_needed = max(1, -(-max_results // 10))  # ceil division

        query = f"{expanded_keywords} in {location}" if location else expanded_keywords

        while len(jobs) < max_results and page <= pages_needed:
            params: Dict[str, Any] = {"query": query, "page": page, "num_pages": 1}

            if date_posted:
                params["date_posted"] = date_posted

            if work_type:
                if work_type.lower() == "remote":
                    params["remote_jobs_only"] = "true"
                elif "remote" not in work_type.lower():
                    params["remote_jobs_only"] = "false"
                # mixed (remote,hybrid) — omit the flag for broader results

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
                logger.info(f"JSearch returned 0 results for query='{query}' page={page} date_posted={date_posted}")
                break

            for raw in raw_jobs:
                if len(jobs) >= max_results:
                    break
                normalized = self._normalize(raw)
                if normalized:
                    jobs.append(normalized)
            page += 1

        logger.info(
            f"JSearch: {len(jobs)} jobs for '{expanded_keywords}' in '{location}' "
            f"(original='{keywords}', date_posted={date_posted})"
        )
        return jobs

    def _normalize(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normalize a raw JSearch job.

        job_url must be non-empty — it is stored as source_url (UNIQUE column).
        Empty job_url causes IntegrityError on the second insert which rolls
        back silently, swallowing the whole batch with zero error counts.
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
            job_url     = raw.get("job_url", "").strip()

            if not job_url:
                logger.warning(f"Skipping job with no job_url: '{title}' @ '{company}'")
                return None

            if not title or not company:
                logger.debug(f"Skipping job missing title or company: title='{title}' company='{company}'")
                return None

            # description can be very short for some aggregator listings — keep them
            # but log so we can monitor quality
            if not description:
                logger.debug(f"Job has no description: '{title}' @ '{company}' — skipping")
                return None

            apply_link = (raw.get("job_apply_link") or job_url).strip()
            posted_at  = raw.get("job_posted_at_datetime_utc")

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
