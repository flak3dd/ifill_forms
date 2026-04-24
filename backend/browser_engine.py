import asyncio
import json
import time
import random
from typing import Dict, Any, List, Optional, Tuple
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import stealth_async
from .anti_bot import build_anti_bot_context_options, install_anti_bot_initial_scripts
from .config import settings
from .models import Profile
import logging

logger = logging.getLogger(__name__)

class BrowserEngine:
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        
    async def initialize(self):
        """Initialize Playwright browser with stealth settings"""
        self.playwright = await async_playwright().start()
        
        # Launch browser with stealth options
        launch_options = {
            "headless": settings.BROWSER_HEADLESS,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
        }
        
        self.browser = await self.playwright.chromium.launch(**launch_options)
        logger.info("Browser engine initialized")
    
    async def create_context(self, job_id: str, use_stealth: bool = True) -> BrowserContext:
        """Create a new browser context for a job"""
        context_options = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "permissions": ["geolocation", "notifications"],
            "geolocation": {"latitude": 40.7128, "longitude": -74.0060},  # NYC
            "extra_http_headers": {
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        }
        
        context = await self.browser.new_context(**context_options)
        
        if use_stealth:
            await install_anti_bot_initial_scripts(context)
            await stealth_async(context)
        
        self.contexts[job_id] = context
        return context
    
    async def get_page(self, job_id: str, context: Optional[BrowserContext] = None) -> Page:
        """Get or create a page for the job"""
        if job_id not in self.pages:
            if context is None:
                context = await self.create_context(job_id)
            page = await context.new_page()
            
            # Set up console logging
            page.on("console", lambda msg: logger.info(f"Browser console [{msg.type}]: {msg.text}"))
            page.on("pageerror", lambda error: logger.error(f"Page error: {error}"))
            
            self.pages[job_id] = page
        
        return self.pages[job_id]
    
    async def navigate_to(self, job_id: str, url: str, wait_for: Optional[str] = None) -> bool:
        """Navigate to a URL and wait for optional selector"""
        try:
            page = await self.get_page(job_id)
            
            # Add random delay to seem more human
            await self.human_delay(0.5, 2.0)
            
            response = await page.goto(url, wait_until="networkidle", timeout=settings.BROWSER_TIMEOUT)
            
            if response.status >= 400:
                logger.error(f"Navigation failed with status {response.status}")
                return False
            
            if wait_for:
                await page.wait_for_selector(wait_for, timeout=10000)
            
            return True
            
        except Exception as e:
            logger.error(f"Navigation error: {str(e)}")
            return False
    
    async def fill_field(self, job_id: str, field_info: Dict[str, Any], value: str) -> bool:
        """Fill a form field with human-like behavior"""
        try:
            page = await self.get_page(job_id)
            locator = self._build_locator(page, field_info)
            
            if not locator:
                return False
            
            # Wait for field to be visible
            await locator.wait_for(state="visible", timeout=5000)
            
            # Click field first to focus
            await locator.click()
            await self.human_delay(0.1, 0.3)
            
            # Clear existing content
            await locator.fill("")
            
            # Type with human-like speed
            await locator.type(value, delay=random.uniform(50, 150))
            
            # Add small delay after typing
            await self.human_delay(0.2, 0.5)
            
            return True
            
        except Exception as e:
            logger.error(f"Field filling error: {str(e)}")
            return False
    
    async def select_option(self, job_id: str, field_info: Dict[str, Any], value: str) -> bool:
        """Select an option from dropdown"""
        try:
            page = await self.get_page(job_id)
            locator = self._build_locator(page, field_info)
            
            if not locator:
                return False
            
            await locator.wait_for(state="visible", timeout=5000)
            await locator.select_option(value)
            await self.human_delay(0.2, 0.5)
            
            return True
            
        except Exception as e:
            logger.error(f"Option selection error: {str(e)}")
            return False
    
    async def click_button(self, job_id: str, button_info: Dict[str, Any]) -> bool:
        """Click a button with human-like behavior"""
        try:
            page = await self.get_page(job_id)
            locator = self._build_locator(page, button_info)
            
            if not locator:
                return False
            
            # Wait for button to be enabled
            await locator.wait_for(state="visible", timeout=5000)
            
            # Scroll into view if needed
            await locator.scroll_into_view_if_needed()
            await self.human_delay(0.2, 0.5)
            
            # Click with delay
            await locator.click()
            await self.human_delay(0.5, 1.5)
            
            return True
            
        except Exception as e:
            logger.error(f"Button click error: {str(e)}")
            return False
    
    async def wait_for_navigation(self, job_id: str, timeout: int = 10000) -> bool:
        """Wait for page navigation"""
        try:
            page = await self.get_page(job_id)
            await page.wait_for_load_state("networkidle", timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"Navigation wait error: {str(e)}")
            return False
    
    async def take_screenshot(self, job_id: str, filename: Optional[str] = None) -> str:
        """Take a screenshot of the current page"""
        try:
            page = await self.get_page(job_id)
            
            if not filename:
                filename = f"screenshot_{job_id}_{int(time.time())}.png"
            
            await page.screenshot(path=filename, full_page=True)
            return filename
            
        except Exception as e:
            logger.error(f"Screenshot error: {str(e)}")
            return ""
    
    async def extract_text(self, job_id: str, selector: str) -> Optional[str]:
        """Extract text from an element"""
        try:
            page = await self.get_page(job_id)
            element = await page.wait_for_selector(selector, timeout=5000)
            return await element.inner_text()
        except Exception as e:
            logger.error(f"Text extraction error: {str(e)}")
            return None
    
    async def check_success_indicators(self, job_id: str, indicators: Dict[str, Any]) -> bool:
        """Check if submission was successful based on indicators"""
        try:
            page = await self.get_page(job_id)
            
            # Check for success text
            if "text_contains" in indicators:
                page_text = await page.inner_text("body")
                if indicators["text_contains"] in page_text:
                    return True
            
            # Check for success URL pattern
            if "url_pattern" in indicators:
                current_url = page.url
                if indicators["url_pattern"] in current_url:
                    return True
            
            # Check for success selector
            if "selector" in indicators:
                element = await page.query_selector(indicators["selector"])
                if element:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Success check error: {str(e)}")
            return False
    
    def _build_locator(self, page: Page, field_info: Dict[str, Any]):
        """Build a Playwright locator from field information"""
        try:
            locator_info = field_info.get("locator", {})
            
            if "role" in locator_info:
                return page.get_by_role(locator_info["role"], name=locator_info.get("name"))
            elif "text" in locator_info:
                return page.get_by_text(locator_info["text"])
            elif "label" in locator_info:
                return page.get_by_label(locator_info["label"])
            elif "placeholder" in locator_info:
                return page.get_by_placeholder(locator_info["placeholder"])
            elif "selector" in locator_info:
                return page.locator(locator_info["selector"])
            elif "type" in locator_info:
                return page.locator(f"[type='{locator_info['type']}']")
            else:
                # Fallback to semantic search
                return page.locator(f"[data-semantic='{field_info.get('semantic_tag', '')}']")
                
        except Exception as e:
            logger.error(f"Locator building error: {str(e)}")
            return None
    
    async def human_delay(self, min_seconds: float, max_seconds: float):
        """Add human-like random delay"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
    
    async def execute_profile(self, job_id: str, profile: Profile, data_row: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a complete profile with a data row"""
        result = {
            "success": False,
            "steps_completed": [],
            "errors": [],
            "screenshots": [],
            "extracted_data": {},
            "execution_time": 0
        }
        
        start_time = time.time()
        
        try:
            # Navigate to base URL
            if await self.navigate_to(job_id, profile.base_url):
                result["steps_completed"].append("navigate")
                screenshot = await self.take_screenshot(job_id)
                if screenshot:
                    result["screenshots"].append(screenshot)
            
            # Execute workflow steps
            for step_name, step_data in profile.steps.items():
                try:
                    if step_data["type"] == "fill":
                        await self._execute_fill_step(job_id, step_data, data_row, profile.field_mappings, result)
                    elif step_data["type"] == "click":
                        await self._execute_click_step(job_id, step_data, result)
                    elif step_data["type"] == "wait":
                        await self._execute_wait_step(job_id, step_data, result)
                    elif step_data["type"] == "extract":
                        await self._execute_extract_step(job_id, step_data, result)
                    
                    result["steps_completed"].append(step_name)
                    
                except Exception as e:
                    error_msg = f"Step '{step_name}' failed: {str(e)}"
                    result["errors"].append(error_msg)
                    logger.error(error_msg)
                    break
            
            # Check success indicators
            if profile.success_indicators:
                result["success"] = await self.check_success_indicators(job_id, profile.success_indicators)
            else:
                result["success"] = len(result["errors"]) == 0
            
        except Exception as e:
            result["errors"].append(f"Profile execution failed: {str(e)}")
            logger.error(f"Profile execution failed: {str(e)}")
        
        finally:
            result["execution_time"] = time.time() - start_time
            
            # Take final screenshot
            screenshot = await self.take_screenshot(job_id, f"final_{job_id}_{int(time.time())}.png")
            if screenshot:
                result["screenshots"].append(screenshot)
        
        return result
    
    async def _execute_fill_step(self, job_id: str, step_data: Dict[str, Any], data_row: Dict[str, Any], 
                                field_mappings: Dict[str, Any], result: Dict[str, Any]):
        """Execute a fill step"""
        for field_info in step_data.get("fields", []):
            semantic_tag = field_info.get("semantic")
            
            # Find the CSV column for this field
            csv_column = None
            for col, mapping in field_mappings.items():
                if mapping.get("semantic") == semantic_tag:
                    csv_column = col
                    break
            
            if csv_column and csv_column in data_row:
                value = str(data_row[csv_column])
                
                # Apply transformation if specified
                transformation = field_mappings.get(csv_column, {}).get("transformation")
                if transformation:
                    value = self._apply_transformation(value, transformation)
                
                # Fill the field
                if field_info.get("type") == "select":
                    await self.select_option(job_id, field_info, value)
                else:
                    await self.fill_field(job_id, field_info, value)
    
    async def _execute_click_step(self, job_id: str, step_data: Dict[str, Any], result: Dict[str, Any]):
        """Execute a click step"""
        button_info = step_data.get("button", {})
        await self.click_button(job_id, button_info)
        
        # Wait for navigation if expected
        if step_data.get("wait_for_navigation", False):
            await self.wait_for_navigation(job_id)
    
    async def _execute_wait_step(self, job_id: str, step_data: Dict[str, Any], result: Dict[str, Any]):
        """Execute a wait step"""
        wait_type = step_data.get("wait_type", "time")
        
        if wait_type == "time":
            duration = step_data.get("duration", 1.0)
            await asyncio.sleep(duration)
        elif wait_type == "selector":
            selector = step_data.get("selector")
            if selector:
                page = await self.get_page(job_id)
                await page.wait_for_selector(selector, timeout=10000)
        elif wait_type == "network":
            page = await self.get_page(job_id)
            await page.wait_for_load_state("networkidle", timeout=10000)
    
    async def _execute_extract_step(self, job_id: str, step_data: Dict[str, Any], result: Dict[str, Any]):
        """Execute an extract step"""
        extractions = step_data.get("extractions", {})
        page = await self.get_page(job_id)
        
        for name, selector in extractions.items():
            try:
                element = await page.wait_for_selector(selector, timeout=5000)
                text = await element.inner_text()
                result["extracted_data"][name] = text
            except Exception as e:
                logger.error(f"Extraction failed for '{name}': {str(e)}")
    
    def _apply_transformation(self, value: str, transformation: str) -> str:
        """Apply data transformation"""
        if transformation == "title_case":
            return value.title()
        elif transformation == "upper_case":
            return value.upper()
        elif transformation == "lower_case":
            return value.lower()
        elif transformation == "phone_format":
            # Basic phone formatting
            digits = ''.join(filter(str.isdigit, value))
            if len(digits) == 10:
                return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
            return value
        else:
            return value
    
    async def test_profile(self, profile: Profile, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test a profile with sample data"""
        job_id = f"test_{int(time.time())}"
        
        try:
            # Create context with headed mode for testing
            context = await self.create_context(job_id, use_stealth=profile.steps.get("use_stealth", True))
            
            # Execute the profile
            result = await self.execute_profile(job_id, profile, test_data)
            
            return result
            
        finally:
            # Cleanup
            await self.cleanup_job(job_id)
    
    async def cleanup_job(self, job_id: str):
        """Clean up resources for a job"""
        if job_id in self.pages:
            await self.pages[job_id].close()
            del self.pages[job_id]
        
        if job_id in self.contexts:
            await self.contexts[job_id].close()
            del self.contexts[job_id]
    
    async def cleanup(self):
        """Clean up all browser resources"""
        for job_id in list(self.pages.keys()):
            await self.cleanup_job(job_id)
        
        if self.browser:
            await self.browser.close()
        
        if self.playwright:
            await self.playwright.stop()
        
        logger.info("Browser engine cleaned up")
