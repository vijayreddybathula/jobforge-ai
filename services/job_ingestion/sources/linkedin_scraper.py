"""LinkedIn job scraper."""

from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, Browser, Page
from packages.common.rate_limiter import RateLimiter
from packages.common.logging import get_logger
import time
import random

logger = get_logger(__name__)


class LinkedInScraper:
    """Scraper for LinkedIn job postings."""

    def __init__(self):
        """Initialize LinkedIn scraper."""
        self.rate_limiter = RateLimiter(key_prefix="ratelimit:linkedin:")
        self.max_jobs_per_hour = 10
        self.base_delay = 2  # Base delay in seconds
        self.max_delay = 5

    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows scraping."""
        is_allowed, count, remaining = self.rate_limiter.check_rate_limit(
            identifier="linkedin", max_requests=self.max_jobs_per_hour, window=3600  # 1 hour
        )

        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded for LinkedIn. Current: {count}, Remaining: {remaining}"
            )
            return False

        logger.debug(
            f"LinkedIn rate limit: {count}/{self.max_jobs_per_hour}, Remaining: {remaining}"
        )
        return True

    def _random_delay(self):
        """Add random delay to mimic human behavior."""
        delay = random.uniform(self.base_delay, self.max_delay)
        time.sleep(delay)

    def scrape_job_url(self, job_url: str, browser: Browser) -> Optional[Dict[str, Any]]:
        """Scrape a single LinkedIn job URL.

        Args:
            job_url: LinkedIn job posting URL
            browser: Playwright browser instance

        Returns:
            Job data dictionary or None
        """
        if not self._check_rate_limit():
            return None

        try:
            page = browser.new_page()

            # Set user agent
            page.set_extra_http_headers(
                {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )

            # Navigate to job page
            page.goto(job_url, wait_until="networkidle", timeout=30000)

            # Wait for content to load
            page.wait_for_timeout(2000)

            # Extract job data
            job_data = {
                "url": job_url,
                "title": self._extract_title(page),
                "company": self._extract_company(page),
                "location": self._extract_location(page),
                "description": self._extract_description(page),
                "html_content": page.content(),
                "posted_at": self._extract_posted_date(page),
            }

            page.close()

            self._random_delay()

            logger.info(f"Scraped LinkedIn job: {job_data['title']} at {job_data['company']}")

            return job_data

        except Exception as e:
            logger.error(f"Failed to scrape LinkedIn job {job_url}: {e}")
            return None

    def scrape_search_results(self, search_url: str, max_jobs: int = 10) -> List[Dict[str, Any]]:
        """Scrape jobs from LinkedIn search results.

        Args:
            search_url: LinkedIn job search URL
            max_jobs: Maximum number of jobs to scrape

        Returns:
            List of job data dictionaries
        """
        jobs: List[Dict[str, Any]] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            try:
                page = browser.new_page()

                # Set user agent
                page.set_extra_http_headers(
                    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )

                # Navigate to search page
                page.goto(search_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                # Extract job URLs from search results
                job_urls = self._extract_job_urls(page, max_jobs)

                logger.info(f"Found {len(job_urls)} job URLs from LinkedIn search")

                # Scrape each job
                for job_url in job_urls:
                    if len(jobs) >= max_jobs:
                        break

                    job_data = self.scrape_job_url(job_url, browser)
                    if job_data:
                        jobs.append(job_data)

                browser.close()

            except Exception as e:
                logger.error(f"LinkedIn search scraping failed: {e}")
                browser.close()

        return jobs

    def _extract_title(self, page: Page) -> str:
        """Extract job title from page."""
        try:
            # LinkedIn job title selector (may need updating)
            title = page.locator("h1.job-title, h1.topcard__title").first.inner_text()
            return title.strip()
        except Exception:
            return ""

    def _extract_company(self, page: Page) -> str:
        """Extract company name from page."""
        try:
            # LinkedIn company selector (may need updating)
            company = page.locator(
                ".topcard__org-name-link, .job-details-jobs-unified-top-card__company-name"
            ).first.inner_text()
            return company.strip()
        except Exception:
            return ""

    def _extract_location(self, page: Page) -> str:
        """Extract job location from page."""
        try:
            # LinkedIn location selector (may need updating)
            location = page.locator(
                ".topcard__flavor--bullet, .job-details-jobs-unified-top-card__bullet"
            ).first.inner_text()
            return location.strip()
        except Exception:
            return ""

    def _extract_description(self, page: Page) -> str:
        """Extract job description from page."""
        try:
            # LinkedIn description selector (may need updating)
            description = page.locator(
                ".description__text, .jobs-description__text"
            ).first.inner_text()
            return description.strip()
        except Exception:
            return ""

    def _extract_posted_date(self, page: Page) -> Optional[str]:
        """Extract posted date from page."""
        try:
            # LinkedIn posted date selector (may need updating)
            date_text = page.locator(".posted-time-ago__text").first.inner_text()
            return date_text.strip()
        except Exception:
            return None

    def _extract_job_urls(self, page: Page, max_urls: int) -> List[str]:
        """Extract job URLs from search results page."""
        urls = []
        try:
            # LinkedIn job link selector (may need updating)
            links = page.locator("a.job-card-list__title, a.base-card__full-link").all()
            for link in links[:max_urls]:
                href = link.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        href = f"https://www.linkedin.com{href}"
                    urls.append(href)
        except Exception as e:
            logger.warning(f"Failed to extract job URLs: {e}")

        return urls
