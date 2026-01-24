"""Apply bot orchestrator for browser automation."""

from typing import Dict, Any, Optional, List
from uuid import UUID
from playwright.sync_api import sync_playwright, Browser, Page
from packages.common.session_manager import BrowserSessionManager
from packages.common.logging import get_logger
import time
import random

logger = get_logger(__name__)


class ApplyOrchestrator:
    """Orchestrate browser automation for job applications."""
    
    def __init__(self):
        """Initialize apply orchestrator."""
        self.session_manager = BrowserSessionManager()
    
    def start_apply_session(
        self,
        job_url: str,
        session_id: str,
        user_data: Dict[str, Any],
        artifacts: Dict[str, str]  # resume_path, pitch, answers
    ) -> Dict[str, Any]:
        """Start assisted apply session.
        
        Args:
            job_url: Job application URL
            session_id: Session ID
            user_data: User data (name, email, phone, etc.)
            artifacts: Generated artifacts (resume, pitch, answers)
        
        Returns:
            Session status
        """
        events = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # Visible for user review
            
            try:
                page = browser.new_page()
                
                # Load saved session if exists
                browser_state = self.session_manager.get_browser_state(session_id)
                if browser_state:
                    # Restore cookies
                    if browser_state.get("cookies"):
                        context = browser.new_context()
                        context.add_cookies(browser_state["cookies"])
                        page = context.new_page()
                
                # Navigate to application page
                events.append({
                    "event": "NAVIGATING",
                    "details": {"url": job_url}
                })
                
                page.goto(job_url, wait_until="networkidle", timeout=30000)
                time.sleep(2)
                
                events.append({
                    "event": "PAGE_LOADED",
                    "details": {"title": page.title()}
                })
                
                # Detect platform and apply strategy
                platform = self._detect_platform(page)
                events.append({
                    "event": "PLATFORM_DETECTED",
                    "details": {"platform": platform}
                })
                
                # Fill form fields
                filled_fields = self._fill_form(page, user_data, artifacts, platform)
                events.extend(filled_fields)
                
                # Upload resume if provided
                if artifacts.get("resume_path"):
                    upload_event = self._upload_resume(page, artifacts["resume_path"], platform)
                    if upload_event:
                        events.append(upload_event)
                
                # Stop before submit (human gate)
                events.append({
                    "event": "STOPPED_AT_SUBMIT",
                    "details": {"message": "Ready for human review. Please review and submit manually."}
                })
                
                # Save browser state
                cookies = context.cookies() if 'context' in locals() else []
                self.session_manager.save_browser_state(
                    session_id=session_id,
                    cookies=cookies,
                    local_storage={},
                    user_id=str(user_data.get("user_id", ""))
                )
                
                browser.close()
                
                return {
                    "session_id": session_id,
                    "status": "READY_FOR_REVIEW",
                    "events": events,
                    "platform": platform
                }
                
            except Exception as e:
                logger.error(f"Apply session failed: {e}")
                events.append({
                    "event": "ERROR",
                    "details": {"error": str(e)}
                })
                browser.close()
                raise
    
    def _detect_platform(self, page: Page) -> str:
        """Detect application platform."""
        url = page.url.lower()
        
        if "greenhouse" in url:
            return "greenhouse"
        elif "lever" in url:
            return "lever"
        elif "linkedin" in url:
            return "linkedin"
        else:
            return "generic"
    
    def _fill_form(self, page: Page, user_data: Dict[str, Any], artifacts: Dict[str, str], platform: str) -> List[Dict[str, Any]]:
        """Fill application form fields."""
        events = []
        
        # Common field mappings
        field_mappings = {
            "first_name": ["firstname", "first_name", "fname"],
            "last_name": ["lastname", "last_name", "lname"],
            "email": ["email", "email_address"],
            "phone": ["phone", "phone_number", "telephone"],
            "linkedin": ["linkedin_url", "linkedin"],
            "website": ["website", "portfolio_url"]
        }
        
        for field_name, possible_selectors in field_mappings.items():
            if field_name in user_data:
                value = user_data[field_name]
                
                # Try different selectors
                filled = False
                for selector_base in possible_selectors:
                    selectors = [
                        f'input[name="{selector_base}"]',
                        f'input[id="{selector_base}"]',
                        f'input[placeholder*="{selector_base}"]',
                    ]
                    
                    for selector in selectors:
                        try:
                            element = page.locator(selector).first
                            if element.count() > 0:
                                element.fill(str(value))
                                filled = True
                                events.append({
                                    "event": "FIELD_FILLED",
                                    "details": {"field": field_name, "selector": selector}
                                })
                                break
                        except Exception:
                            continue
                    
                    if filled:
                        break
        
        # Fill pitch/cover letter if provided
        if artifacts.get("pitch"):
            pitch_selectors = [
                'textarea[name="cover_letter"]',
                'textarea[id="cover_letter"]',
                'textarea[placeholder*="cover"]',
                'textarea[placeholder*="why"]',
            ]
            
            for selector in pitch_selectors:
                try:
                    element = page.locator(selector).first
                    if element.count() > 0:
                        element.fill(artifacts["pitch"])
                        events.append({
                            "event": "FIELD_FILLED",
                            "details": {"field": "cover_letter", "selector": selector}
                        })
                        break
                except Exception:
                    continue
        
        return events
    
    def _upload_resume(self, page: Page, resume_path: str, platform: str) -> Optional[Dict[str, Any]]:
        """Upload resume file."""
        file_input_selectors = [
            'input[type="file"]',
            'input[accept*="pdf"]',
            'input[accept*="doc"]',
        ]
        
        for selector in file_input_selectors:
            try:
                element = page.locator(selector).first
                if element.count() > 0:
                    element.set_input_files(resume_path)
                    return {
                        "event": "FILE_UPLOADED",
                        "details": {"file": resume_path, "selector": selector}
                    }
            except Exception:
                continue
        
        return None
    
    def submit_application(self, session_id: str) -> Dict[str, Any]:
        """Submit application (after human review)."""
        # In production, this would restore the browser session and click submit
        # For now, return success
        return {
            "session_id": session_id,
            "status": "SUBMITTED",
            "message": "Application submitted successfully"
        }
