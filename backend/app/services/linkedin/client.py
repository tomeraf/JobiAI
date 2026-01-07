"""
LinkedIn Client using Playwright persistent context.

Uses a persistent browser context to maintain login state across sessions.
This is more reliable than cookie extraction as it maintains the full
browser environment including localStorage, sessionStorage, and cookies.
"""
import asyncio
import os
import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Path to store browser data (persistent context)
BROWSER_DATA_PATH = Path("linkedin_data/browser_context")

# Speed mode - set to false for more human-like delays (safer)
# true = fast mode (~300ms delays), false = safe mode (~1000ms delays)
FAST_MODE = os.getenv("FAST_MODE", "true").lower() == "true"

# Delay multiplier based on mode
DELAY_MS = 300 if FAST_MODE else 1000

# Create a dedicated thread pool for Playwright operations
_playwright_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")

# Retry delays in seconds: 0.2, 0.5, 1.5, 2.0
RETRY_DELAYS = [0.2, 0.5, 1.5, 2.0]

# Try to import playwright
try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    logger.warning("playwright not installed - browser features disabled")

# Try to import playwright-stealth
try:
    from playwright_stealth import stealth_sync
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False
    logger.warning("playwright-stealth not installed - stealth features disabled")


def _run_sync_playwright(func, *args, **kwargs):
    """
    Run a synchronous Playwright function in a way that works on Windows.

    Playwright on Windows requires ProactorEventLoop for subprocess support.
    This sets up the correct event loop policy before running sync_playwright().
    """
    # On Windows, we need to set the event loop policy for subprocesses
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return func(*args, **kwargs)


async def _run_playwright_async(func, *args, **kwargs):
    """
    Run a synchronous Playwright function asynchronously on Windows.

    Uses a dedicated thread pool with the correct event loop policy.
    """
    loop = asyncio.get_event_loop()

    def wrapper():
        return _run_sync_playwright(func, *args, **kwargs)

    return await loop.run_in_executor(_playwright_executor, wrapper)


class WorkflowAbortedException(Exception):
    """Raised when workflow is aborted by user."""
    pass


class MissingHebrewNamesException(Exception):
    """Raised when Hebrew name translations are needed but not available.

    This exception is raised during message sending when we encounter names
    that need Hebrew translations. The workflow should pause and ask the user
    for translations.
    """
    def __init__(self, missing_names: list[str], first_degree_found: list[dict] = None):
        self.missing_names = missing_names
        self.first_degree_found = first_degree_found or []
        super().__init__(f"Missing Hebrew translations for: {', '.join(missing_names)}")


import random

def _apply_stealth(page):
    """Apply stealth patches to a page to avoid bot detection."""
    if HAS_STEALTH:
        try:
            stealth_sync(page)
            logger.debug("Stealth patches applied to page")
        except Exception as e:
            logger.warning(f"Failed to apply stealth patches: {e}")
    else:
        logger.warning("Stealth not available - browser may be detected as automated")


def _human_delay(min_ms: int = 500, max_ms: int = 2000):
    """Add a random human-like delay."""
    delay = random.randint(min_ms, max_ms) / 1000.0
    import time
    time.sleep(delay)


def _human_delay_short():
    """Short delay for between actions (~300ms)."""
    _human_delay(200, 400)


def _human_delay_medium():
    """Medium delay for page loads (~300ms)."""
    _human_delay(250, 450)


def _human_delay_long():
    """Long delay for major actions like messaging (~300ms)."""
    _human_delay(300, 500)


class LinkedInClient:
    """
    LinkedIn client using Playwright with persistent browser context.

    Uses a singleton pattern - the instance state persists across requests.
    The browser context is stored on disk and reused between sessions.
    """

    _instance: "LinkedInClient | None" = None

    def __new__(cls):
        """Ensure singleton - only one instance ever exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._logged_in = False
            cls._instance._email = None
            cls._instance._name = None
            cls._instance._playwright = None
            cls._instance._browser = None
            cls._instance._context = None
            cls._instance._abort_requested = False
            cls._instance._current_job_id = None
            cls._instance._queued_jobs = []  # Jobs waiting to run
        return cls._instance

    def __init__(self):
        pass

    @classmethod
    def get_instance(cls) -> "LinkedInClient":
        """Get singleton instance of the client."""
        return cls()

    def request_abort(self, job_id: int | None = None):
        """Request the workflow to abort. If job_id is specified, only abort that job."""
        self._abort_requested = True
        logger.info(f"Abort requested for job {job_id if job_id else 'current'}")

    def clear_abort(self):
        """Clear the abort flag."""
        self._abort_requested = False

    def is_abort_requested(self) -> bool:
        """Check if abort has been requested."""
        return self._abort_requested

    def set_current_job(self, job_id: int | None):
        """Set the currently running job ID."""
        self._current_job_id = job_id

    def get_current_job(self) -> int | None:
        """Get the currently running job ID."""
        return self._current_job_id

    def add_to_queue(self, job_id: int):
        """Add a job to the queue of jobs waiting to run."""
        if job_id not in self._queued_jobs:
            self._queued_jobs.append(job_id)
            logger.info(f"Job {job_id} added to queue. Queue: {self._queued_jobs}")

    def remove_from_queue(self, job_id: int):
        """Remove a job from the queue."""
        if job_id in self._queued_jobs:
            self._queued_jobs.remove(job_id)
            logger.info(f"Job {job_id} removed from queue. Queue: {self._queued_jobs}")

    def get_queued_jobs(self) -> list[int]:
        """Get list of job IDs waiting in queue."""
        return list(self._queued_jobs)

    def is_job_queued(self, job_id: int) -> bool:
        """Check if a job is in the queue."""
        return job_id in self._queued_jobs

    def check_abort(self):
        """Check if abort was requested and raise exception if so."""
        if self._abort_requested:
            raise WorkflowAbortedException("Workflow aborted by user")

    def _wait_with_abort_check(self, page, ms: int):
        """
        Wait for specified milliseconds, but check for abort every 500ms.
        This allows the workflow to be aborted during long waits.
        """
        remaining = ms
        while remaining > 0:
            self.check_abort()
            wait_time = min(remaining, 500)  # Check every 500ms max
            page.wait_for_timeout(wait_time)
            remaining -= wait_time

    def _ensure_data_dir(self):
        """Ensure browser data directory exists."""
        BROWSER_DATA_PATH.mkdir(parents=True, exist_ok=True)

    def _retry_click(self, page, selectors: list[str], action_name: str) -> bool:
        """
        Retry clicking an element with progressive delays.

        Tries each selector, then waits and retries with delays: 0.2s, 0.5s, 1.5s, 2.0s
        If all retries fail, raises an exception with the action name.

        Args:
            page: Playwright page object
            selectors: List of CSS selectors to try
            action_name: Human-readable name for error messages (e.g., "click People tab")

        Returns:
            True if click succeeded

        Raises:
            Exception if all retries fail
        """
        for attempt, delay in enumerate([0] + RETRY_DELAYS):  # First attempt has no delay
            if delay > 0:
                logger.info(f"Retry {attempt}/{len(RETRY_DELAYS)} for {action_name} - waiting {delay}s...")
                page.wait_for_timeout(int(delay * 1000))

            for selector in selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        logger.info(f"Found element for '{action_name}' with selector: {selector}")
                        element.click()
                        page.wait_for_timeout(DELAY_MS)
                        return True
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

            if delay == 0:
                logger.info(f"First attempt for '{action_name}' failed, starting retries...")

        # All retries exhausted
        error_msg = f"Failed to {action_name} after {len(RETRY_DELAYS)} retries"
        logger.error(error_msg)
        raise Exception(error_msg)

    def _retry_find(self, page, selectors: list[str], action_name: str):
        """
        Retry finding an element with progressive delays.

        Tries each selector, then waits and retries with delays: 0.2s, 0.5s, 1.5s, 2.0s
        If all retries fail, raises an exception with the action name.

        Args:
            page: Playwright page object
            selectors: List of CSS selectors to try
            action_name: Human-readable name for error messages (e.g., "find search input")

        Returns:
            The found element

        Raises:
            Exception if all retries fail
        """
        for attempt, delay in enumerate([0] + RETRY_DELAYS):  # First attempt has no delay
            if delay > 0:
                logger.info(f"Retry {attempt}/{len(RETRY_DELAYS)} for {action_name} - waiting {delay}s...")
                page.wait_for_timeout(int(delay * 1000))

            for selector in selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        logger.info(f"Found element for '{action_name}' with selector: {selector}")
                        return element
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

            if delay == 0:
                logger.info(f"First attempt for '{action_name}' failed, starting retries...")

        # All retries exhausted
        error_msg = f"Failed to {action_name} after {len(RETRY_DELAYS)} retries"
        logger.error(error_msg)
        raise Exception(error_msg)

    def _retry_find_in_element(self, page, element, selectors: list[str], action_name: str):
        """
        Retry finding an element within a parent element with progressive delays.

        Args:
            page: Playwright page object (for wait_for_timeout)
            element: Parent element to search within
            selectors: List of CSS selectors to try
            action_name: Human-readable name for error messages

        Returns:
            The found element, or None if not found after retries
        """
        for attempt, delay in enumerate([0] + RETRY_DELAYS):
            if delay > 0:
                logger.debug(f"Retry {attempt}/{len(RETRY_DELAYS)} for {action_name} - waiting {delay}s...")
                page.wait_for_timeout(int(delay * 1000))

            for selector in selectors:
                try:
                    found = element.query_selector(selector)
                    if found:
                        logger.debug(f"Found element for '{action_name}' with selector: {selector}")
                        return found
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

        # Return None instead of raising - caller decides if this is fatal
        logger.debug(f"Could not find element for '{action_name}' after retries")
        return None

    def _retry_click_in_element(self, page, element, selectors: list[str], action_name: str) -> bool:
        """
        Retry clicking an element within a parent element with progressive delays.

        Args:
            page: Playwright page object (for wait_for_timeout)
            element: Parent element to search within
            selectors: List of CSS selectors to try
            action_name: Human-readable name for error messages

        Returns:
            True if click succeeded, False otherwise
        """
        found = self._retry_find_in_element(page, element, selectors, action_name)
        if found:
            found.click()
            page.wait_for_timeout(DELAY_MS)
            return True
        return False

    async def login_with_browser(self) -> bool:
        """
        Open a browser window for manual LinkedIn login.

        Uses a persistent browser context so the login state is saved
        and can be reused in future sessions.

        Returns:
            True if login successful
        """
        if not HAS_PLAYWRIGHT:
            logger.error("playwright not installed. Run: pip install playwright && playwright install chromium")
            return False

        try:
            logger.info("Opening browser for LinkedIn login...")
            self._ensure_data_dir()

            # Run in dedicated Playwright thread with correct event loop for Windows
            result = await _run_playwright_async(self._browser_login_flow)

            if result:
                self._logged_in = True
                self._name = result.get("name")
                self._email = result.get("email")
                logger.info(f"LinkedIn login successful! Welcome {self._name}")
                return True
            else:
                logger.error("Login cancelled or failed")
                return False

        except Exception as e:
            logger.error(f"Browser login failed: {e}")
            self._logged_in = False
            return False

    def _browser_login_flow(self) -> dict | None:
        """
        Synchronous browser login flow using Playwright persistent context.
        Opens browser, waits for login, saves context to disk.
        """
        context = None

        try:
            with sync_playwright() as p:
                # Launch browser with persistent context
                # This saves all browser data (cookies, localStorage, etc.) to disk
                context = p.chromium.launch_persistent_context(
                    str(BROWSER_DATA_PATH),
                    headless=False,
                    no_viewport=True,  # Required for --start-maximized to work
                    args=["--start-maximized"],
                )

                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(10000)  # 10 second timeout instead of 30
                _apply_stealth(page)
                page.bring_to_front()  # Bring browser window to foreground

                # Force window to foreground on Windows
                try:
                    import win32gui
                    import win32con
                    import time as t
                    t.sleep(0.5)  # Wait for window to be created

                    def bring_chromium_to_front(hwnd, _):
                        title = win32gui.GetWindowText(hwnd)
                        if "Chromium" in title or "LinkedIn" in title:
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                            win32gui.SetForegroundWindow(hwnd)
                            return False  # Stop enumeration
                        return True

                    win32gui.EnumWindows(bring_chromium_to_front, None)
                except Exception as e:
                    logger.debug(f"Could not bring window to front: {e}")

                # First, go to LinkedIn logout to ensure fresh login
                logger.info("Clearing any existing LinkedIn session...")
                try:
                    page.goto("https://www.linkedin.com/m/logout/", wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(1000)
                except Exception as e:
                    # Browser might be closed already
                    logger.info(f"Browser closed during logout: {e}")
                    return None

                # Now go to login page
                try:
                    page.goto("https://www.linkedin.com/login")
                except Exception as e:
                    logger.info(f"Browser closed: {e}")
                    return None

                logger.info("Browser opened - please login to LinkedIn")
                logger.info("The browser will close automatically when you're logged in")

                # Poll for login success or browser close
                logger.info("Waiting for you to login...")
                import time
                start_time = time.time()
                timeout_seconds = 300  # 5 minutes

                while True:
                    # Check if we've timed out
                    if time.time() - start_time > timeout_seconds:
                        logger.info("Login timed out")
                        try:
                            context.close()
                        except:
                            pass
                        return None

                    # Check if page/browser is closed
                    try:
                        if page.is_closed():
                            logger.info("Login cancelled - browser was closed")
                            return None
                    except:
                        logger.info("Login cancelled - browser was closed")
                        return None

                    # Check current URL - this will throw if page is closed
                    try:
                        current_url = page.url
                        if "/feed" in current_url or "/mynetwork" in current_url or "/in/" in current_url:
                            logger.info("Login detected! Getting profile info...")
                            break
                    except Exception as e:
                        # Page might be closed
                        logger.info(f"Login cancelled - page no longer accessible: {e}")
                        return None

                    # Wait a bit before checking again
                    try:
                        page.wait_for_timeout(500)
                    except:
                        logger.info("Login cancelled - browser was closed during wait")
                        return None

                # Get profile info from the page
                try:
                    profile = self._get_profile_from_page(page)
                    context.close()
                    return profile
                except Exception as e:
                    logger.error(f"Error getting profile: {e}")
                    try:
                        context.close()
                    except:
                        pass
                    return None

        except Exception as e:
            # Handle browser closed by user or other errors
            error_str = str(e).lower()
            if "target page" in error_str or "closed" in error_str or "target crash" in error_str:
                logger.info("Login cancelled - browser was closed")
            else:
                logger.error(f"Browser login failed: {e}")
            if context:
                try:
                    context.close()
                except:
                    pass
            return None

    def _get_profile_from_page(self, page: "Page") -> dict:
        """Extract profile info from the LinkedIn page."""
        try:
            # Try to get name from the nav bar (faster than loading profile page)
            name = None
            try:
                # Look for the profile photo/name in the nav - it's usually there on any LinkedIn page
                nav_profile = page.query_selector("img.global-nav__me-photo")
                if nav_profile:
                    name = nav_profile.get_attribute("alt")
                    if name:
                        name = name.replace("Photo of ", "").strip()
            except:
                pass

            # If we couldn't get it from nav, try going to profile page
            if not name:
                try:
                    page.goto("https://www.linkedin.com/in/me/", timeout=15000)
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    name_element = page.query_selector("h1")
                    if name_element:
                        name = name_element.inner_text().strip()
                except Exception as e:
                    logger.warning(f"Could not load profile page: {e}")

            return {"name": name, "email": None}
        except Exception as e:
            logger.error(f"Error getting profile: {e}")
            return {"name": None, "email": None}

    async def check_session(self) -> bool:
        """Check if we have a valid LinkedIn session."""
        logger.info(f"check_session called: _logged_in={self._logged_in}")

        # If we think we're logged in, verify it
        if self._logged_in:
            return True

        # Check if we have a persistent context saved
        if not BROWSER_DATA_PATH.exists():
            logger.info("No saved browser context found")
            return False

        # Try to verify the session by checking if we can access LinkedIn
        try:
            result = await _run_playwright_async(self._verify_session)

            if result:
                self._logged_in = True
                self._name = result.get("name")
                logger.info(f"Session valid, logged in as: {self._name}")
                return True
            else:
                logger.info("Session expired or invalid")
                return False

        except Exception as e:
            logger.error(f"Session check failed: {e}")
            return False

    def _verify_session(self) -> dict | None:
        """Verify the saved session is still valid."""
        if not HAS_PLAYWRIGHT:
            return None

        with sync_playwright() as p:
            try:
                # Launch browser with persistent context (headless for verification)
                context = p.chromium.launch_persistent_context(
                    str(BROWSER_DATA_PATH),
                    headless=True,  # Headless for background check
                )

                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(10000)  # 10 second timeout instead of 30
                _apply_stealth(page)

                # Try to access LinkedIn feed
                page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)

                # Check if we're logged in (not redirected to login)
                current_url = page.url
                if "/login" in current_url or "/checkpoint" in current_url:
                    context.close()
                    return None

                # Get profile info
                profile = self._get_profile_from_page(page)
                context.close()
                return profile

            except Exception as e:
                logger.error(f"Session verification failed: {e}")
                return None

    async def logout(self):
        """Clear saved session data."""
        import shutil

        self._logged_in = False
        self._name = None
        self._email = None

        # Remove the browser data directory
        if BROWSER_DATA_PATH.exists():
            try:
                shutil.rmtree(BROWSER_DATA_PATH)
                logger.info("LinkedIn browser context cleared")
            except Exception as e:
                logger.error(f"Error clearing browser context: {e}")

        # Also remove cookies.json if it exists
        cookies_file = BROWSER_DATA_PATH.parent / "cookies.json"
        if cookies_file.exists():
            try:
                cookies_file.unlink()
                logger.info("LinkedIn cookies cleared")
            except Exception as e:
                logger.error(f"Error clearing cookies: {e}")

    async def get_profile_info(self) -> dict:
        """Get the logged-in user's profile info."""
        return {
            "name": self._name,
            "email": self._email,
        }

    @property
    def is_logged_in(self) -> bool:
        """Check if currently logged in."""
        return self._logged_in

    # --- LinkedIn Operations (using browser) ---

    async def search_people(
        self,
        keywords: str = None,
        current_company: list[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """
        Search for 2nd degree people at a company using the user's workflow:
        1. Go to feed page
        2. Use search bar to search company name
        3. Click People tab
        4. Filter by 2nd degree connections
        5. Return people (up to limit)
        """
        if not self._logged_in:
            logger.error("Not logged in")
            return []

        return await _run_playwright_async(self._search_2nd_degree_sync, keywords, limit)

    async def search_company_all_degrees(self, company: str, limit: int = 15, message_generator=None, first_degree_only: bool = False) -> dict:
        """
        Search for people at a company - first 1st degree, then 2nd degree, then 3rd+ if needed.
        All in a single browser session for efficiency.

        Args:
            company: Company name to search for
            limit: Maximum results per degree level
            message_generator: Optional function(name, company) -> str to generate message text
                              for 1st degree connections
            first_degree_only: If True, only search for 1st degree connections (skip 2nd/3rd degree fallback)

        Returns:
            dict with 'first_degree', 'second_degree', 'third_plus', and 'messages_sent' lists
        """
        if not self._logged_in:
            logger.error("Not logged in")
            return {"first_degree": [], "second_degree": [], "third_plus": []}

        return await _run_playwright_async(self._search_company_all_degrees_sync, company, limit, message_generator, first_degree_only)

    def _search_company_all_degrees_sync(self, company: str, limit: int, message_generator=None, first_degree_only: bool = False) -> dict:
        """
        Synchronous combined search for 1st, 2nd, and 3rd+ degree connections at a company.
        Keeps browser open between searches.
        For 2nd/3rd+ degree: clicks Connect button directly on search results page.
        For 1st degree: sends messages using the provided message_generator function.

        If first_degree_only=True, only searches for 1st degree and doesn't fall back to 2nd/3rd.
        """
        if not HAS_PLAYWRIGHT:
            logger.error("Playwright not installed!")
            return {"first_degree": [], "second_degree": [], "third_plus": [], "connection_requests_sent": []}

        result = {"first_degree": [], "second_degree": [], "third_plus": [], "connection_requests_sent": []}
        logger.info(f"Starting combined search for connections at: {company}")

        with sync_playwright() as p:
            context = None
            try:
                logger.info(f"Running in {'FAST' if FAST_MODE else 'SAFE'} mode (delays: {DELAY_MS}ms)")

                context = p.chromium.launch_persistent_context(
                    str(BROWSER_DATA_PATH),
                    headless=False,
                    viewport={"width": 1280, "height": 720},
                    args=["--window-size=1300,750", "--window-position=100,100"],  # Override maximized state
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(10000)  # 10 second timeout instead of 30
                _apply_stealth(page)

                # Check for abort before starting
                self.check_abort()

                # Step 1: Go to LinkedIn feed page
                logger.info("Step 1: Going to LinkedIn feed page...")
                page.goto("https://www.linkedin.com/feed/", timeout=60000)
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                self._wait_with_abort_check(page, DELAY_MS)

                # Close any open message overlays before starting
                self._close_all_message_overlays(page)

                # Step 2: Search for company
                logger.info(f"Step 2: Searching for '{company}' in search bar...")
                search_input = self._find_search_input(page)
                if not search_input:
                    logger.error("Could not find search bar!")
                    return result  # finally block will close browser

                search_input.click()
                page.wait_for_timeout(DELAY_MS // 2)
                search_input.fill(company)
                page.wait_for_timeout(DELAY_MS // 2)
                page.keyboard.press("Enter")

                # Wait for search results page to fully load
                logger.info("Waiting for search results to load...")
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)  # Wait 3 seconds for dynamic content to render

                # Step 3: Click People tab
                logger.info("Step 3: Clicking on People tab...")
                if not self._click_people_tab(page):
                    logger.error("Could not find People tab!")
                    return result  # finally block will close browser

                # Check for abort
                self.check_abort()

                # Step 4: Filter by 1st degree and extract
                logger.info("Step 4: Filtering by 1st degree connections...")
                self._apply_connection_filter(page, "1st")
                first_degree = self._extract_search_results(page, company)
                result["first_degree"] = first_degree
                logger.info(f"Found {len(first_degree)} 1st degree connections")

                # Check for abort before sending messages
                self.check_abort()

                # Step 5: If 1st degree found and message_generator provided, send messages from search page
                # Skip if no message_generator (e.g., when Hebrew name translation needed)
                messages_sent_count = 0
                if first_degree and message_generator:
                    logger.info(f"Sending messages to {len(first_degree)} 1st degree connections from search page...")
                    messaged_people = self._send_messages_on_search_page(page, company, message_generator=message_generator, num_pages=1, first_degree_only=first_degree_only)
                    result["messages_sent"] = messaged_people
                    messages_sent_count = len(messaged_people)
                    logger.info(f"Sent {messages_sent_count} messages from search page")
                elif first_degree:
                    logger.info(f"Found {len(first_degree)} 1st degree connections (skipping messages - no generator provided)")

                # Step 6: If no 1st degree found OR all 1st degree were skipped (existing history), switch to 2nd degree
                # This ensures we continue the flow instead of failing when all contacts have been previously messaged
                # UNLESS first_degree_only is True - in that case, we only search for 1st degree
                should_try_2nd_degree = not first_degree or (first_degree and message_generator and messages_sent_count == 0)

                if first_degree_only:
                    # Only searching for 1st degree connections (e.g., checking for accepted requests)
                    if not first_degree:
                        logger.info("First degree only mode: No 1st degree connections found at this company")
                    elif messages_sent_count == 0:
                        logger.info(f"First degree only mode: {len(first_degree)} 1st degree found but all skipped (existing history)")
                    else:
                        logger.info(f"First degree only mode: Sent {messages_sent_count} messages to 1st degree connections")
                    # Don't fall back to 2nd/3rd degree
                elif should_try_2nd_degree:
                    # Check for abort before 2nd degree
                    self.check_abort()

                    if first_degree:
                        logger.info(f"All {len(first_degree)} 1st degree connections were skipped (existing history), trying 2nd degree...")
                    else:
                        logger.info("No 1st degree found, switching to 2nd degree filter...")
                    self._apply_connection_filter(page, "2nd")

                    # Send connection requests directly on search page (max 10 requests)
                    connected_people = self._send_connection_requests_on_search_page(page, company, max_requests=10)
                    result["second_degree"] = connected_people
                    result["connection_requests_sent"] = connected_people
                    logger.info(f"Sent {len(connected_people)} connection requests to 2nd degree people")

                    # Step 6: If we haven't reached 10 requests yet, try 3rd+ degree
                    if len(connected_people) < 10:
                        # Check for abort before 3rd+ degree
                        self.check_abort()

                        remaining_requests = 10 - len(connected_people)
                        logger.info(f"Only {len(connected_people)} 2nd degree requests sent, need {remaining_requests} more - switching to 3rd+ degree...")
                        self._apply_connection_filter(page, "3rd+")

                        # Send remaining connection requests from 3rd+ degree
                        connected_people_3rd = self._send_connection_requests_on_search_page(page, company, max_requests=remaining_requests)
                        result["third_plus"] = connected_people_3rd
                        # Combine both lists for total
                        all_connected = connected_people + connected_people_3rd
                        result["connection_requests_sent"] = all_connected
                        logger.info(f"Sent {len(connected_people_3rd)} connection requests to 3rd+ degree people (total: {len(all_connected)})")

                # Workflow complete
                logger.info("Workflow complete")
                return result

            except WorkflowAbortedException:
                logger.info("Workflow aborted by user")
                raise  # Re-raise to propagate abort

            except MissingHebrewNamesException:
                logger.info("Missing Hebrew names - propagating to workflow orchestrator")
                raise  # Re-raise to let orchestrator handle the pause

            except Exception as e:
                logger.error(f"Combined search failed: {e}", exc_info=True)
                return result

            finally:
                # ALWAYS close the browser, no matter what
                if context:
                    try:
                        logger.info("Closing browser...")
                        context.close()
                        logger.info("Browser closed successfully")
                    except Exception as close_error:
                        logger.warning(f"Error closing browser: {close_error}")

    def _close_all_message_overlays(self, page):
        """
        Close all open message dialogs/overlays on LinkedIn.
        This prevents interference with automation when entering LinkedIn.

        Uses JavaScript execution to find and click close buttons, which is more
        reliable than Playwright selectors for LinkedIn's dynamic DOM.
        """
        logger.info("Closing any open message overlays...")

        # Wait a moment for overlays to be fully rendered
        page.wait_for_timeout(1000)

        # Use JavaScript to close all message overlays - this is the most reliable method
        try:
            closed_count = page.evaluate("""
                () => {
                    let closedCount = 0;

                    // Method 1: Close buttons with aria-label containing "Close" (most reliable)
                    // This catches both "Close your conversation" and "Close your draft conversation"
                    // Also include [role="dialog"] for modal-style dialogs
                    const closeButtonsByAria = document.querySelectorAll(
                        '.msg-overlay-conversation-bubble button[aria-label*="Close"], ' +
                        '.msg-overlay-bubble-header button[aria-label*="Close"], ' +
                        '[role="dialog"] button[aria-label*="Close"]'
                    );
                    closeButtonsByAria.forEach(btn => {
                        try {
                            btn.click();
                            closedCount++;
                        } catch (e) {}
                    });

                    // Method 2: Find conversation bubbles and close them via header controls
                    // (fallback in case aria-label approach misses some)
                    if (closedCount === 0) {
                        const conversationBubbles = document.querySelectorAll('.msg-overlay-conversation-bubble');
                        conversationBubbles.forEach(bubble => {
                            // Find the header close button by its class pattern
                            const closeBtn = bubble.querySelector(
                                '.msg-overlay-bubble-header__control:not(.msg-overlay-conversation-bubble__expand-btn):not(.msg-overlay-bubble-header__control--new-convo-btn)'
                            );
                            if (closeBtn) {
                                try {
                                    closeBtn.click();
                                    closedCount++;
                                } catch (e) {}
                            }
                        });
                    }

                    // Method 3: Close draft conversation dialogs
                    const draftCloseButtons = document.querySelectorAll(
                        'button[aria-label="Close your draft conversation"]'
                    );
                    draftCloseButtons.forEach(btn => {
                        try {
                            btn.click();
                            closedCount++;
                        } catch (e) {}
                    });

                    // Method 4: Press Escape key to close any remaining modals
                    if (closedCount === 0) {
                        document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', keyCode: 27, bubbles: true}));
                    }

                    return closedCount;
                }
            """)

            if closed_count > 0:
                logger.info(f"Closed {closed_count} message overlay(s) via JavaScript")
                # Wait for the overlays to actually close
                page.wait_for_timeout(500)
            else:
                logger.info("No open message overlays found via JS methods")

            # Double-check: if still open, try pressing Escape via Playwright
            still_open = page.evaluate("""
                () => {
                    return !!document.querySelector('.msg-overlay-conversation-bubble, [role="dialog"]');
                }
            """)
            if still_open:
                logger.info("Overlays still detected, pressing Escape via Playwright")
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)

        except Exception as e:
            logger.warning(f"JavaScript overlay close failed: {e}, trying fallback method...")

            # Fallback: try with Playwright selectors
            close_selectors = [
                "button[aria-label='Close your conversation']",
                "button[aria-label='Close your draft conversation']",
                ".msg-overlay-bubble-header__control:not(.msg-overlay-conversation-bubble__expand-btn)",
            ]

            for selector in close_selectors:
                try:
                    close_btns = page.query_selector_all(selector)
                    for btn in close_btns:
                        try:
                            btn.click(force=True)
                            page.wait_for_timeout(300)
                            logger.info(f"Closed overlay with selector: {selector}")
                        except:
                            pass
                except:
                    pass

            # Final fallback: press Escape
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except:
                pass

    def _find_search_input(self, page):
        """Find the LinkedIn search input. Uses retry logic with progressive delays."""
        search_selectors = [
            "input.search-global-typeahead__input",
            "input[placeholder*='Search']",
            "input[aria-label*='Search']",
            ".search-global-typeahead input",
        ]
        return self._retry_find(page, search_selectors, "find search input")

    def _click_people_tab(self, page) -> bool:
        """Click the People tab in search results. Uses retry logic with progressive delays."""
        # Log current URL for debugging
        current_url = page.url
        logger.info(f"Current URL before clicking People tab: {current_url}")

        # If we're already on a people search page, we're good
        if "/search/results/people" in current_url:
            logger.info("Already on people search results page")
            return True

        people_tab_selectors = [
            "button:has-text('People')",
            "a:has-text('People')",
            "[data-test-search-tab='PEOPLE']",
            ".search-reusables__filter-pill-button:has-text('People')",
            ".artdeco-pill:has-text('People')",
            "button.search-reusables__filter-pill-button:has-text('People')",
            "li button:has-text('People')",
            "nav a:has-text('People')",
            ".search-navigation a:has-text('People')",
        ]

        try:
            # Use retry logic with progressive delays
            self._retry_click(page, people_tab_selectors, "click People tab")
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            return True
        except Exception as e:
            # If clicking didn't work after retries, try direct URL navigation as last resort
            logger.info("Retries exhausted for People tab, trying direct URL navigation...")
            try:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(current_url)
                params = parse_qs(parsed.query)
                keywords = params.get('keywords', [''])[0]

                if keywords:
                    people_url = f"https://www.linkedin.com/search/results/people/?keywords={keywords}"
                    logger.info(f"Navigating directly to: {people_url}")
                    page.goto(people_url)
                    page.wait_for_load_state("domcontentloaded", timeout=30000)
                    page.wait_for_timeout(DELAY_MS)
                    return True
            except Exception as nav_error:
                logger.error(f"Direct URL navigation also failed: {nav_error}")

            # Re-raise the original error
            raise e

    def _apply_connection_filter(self, page, degree: str):
        """Apply 1st or 2nd degree connection filter. Uses retry logic with progressive delays."""
        # First, clear any existing degree filters by clicking on active ones to toggle them off
        # LinkedIn filter buttons are toggles - clicking an active one deselects it
        other_degrees = ['1st', '2nd', '3rd+']
        other_degrees.remove(degree) if degree in other_degrees else None

        for other_degree in other_degrees:
            try:
                # Check if this filter is currently active (has aria-pressed="true" or similar)
                active_btn = page.query_selector(f"button:has-text('{other_degree}')[aria-pressed='true']")
                if not active_btn:
                    # Try alternative: check if button has 'selected' class or similar
                    active_btn = page.query_selector(f"button.artdeco-pill--selected:has-text('{other_degree}')")
                if active_btn:
                    logger.info(f"Clearing active {other_degree} filter")
                    active_btn.click()
                    page.wait_for_timeout(500)
            except Exception:
                pass  # Ignore errors clearing other filters

        degree_selectors = [
            f"button:has-text('{degree}')",
            f"button[aria-label*='{degree}']",
            f".search-reusables__filter-pill-button:has-text('{degree}')",
            f"li button:has-text('{degree}')",
            f".artdeco-pill:has-text('{degree}')",
            f"button.artdeco-pill--choice:has-text('{degree}')",
        ]

        try:
            # Use retry logic with progressive delays
            self._retry_click(page, degree_selectors, f"click {degree} degree filter")
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)  # Wait for filtered results to load
            logger.info(f"Successfully applied {degree} filter")
            return True
        except Exception as e:
            # Try dropdown approach as fallback
            logger.info(f"Direct button retries exhausted, trying 'Connections' dropdown for {degree}...")

            # Try to find and click Connections dropdown with retries
            connections_selectors = [
                "button:has-text('Connections')",
                "button[aria-label*='Connections']",
                ".search-reusables__filter-pill-button:has-text('Connections')",
            ]

            try:
                self._retry_click(page, connections_selectors, "click Connections dropdown")
                page.wait_for_timeout(1000)

                # Look for the degree option in the dropdown with retries
                option_selectors = [
                    f"label:has-text('{degree}')",
                    f"input[value*='{degree}']",
                    f"span:has-text('{degree}')",
                ]

                try:
                    self._retry_click(page, option_selectors, f"click {degree} option in dropdown")
                    page.wait_for_timeout(500)

                    # Click "Show results" button with retries
                    show_selectors = [
                        "button:has-text('Show')",
                        "button:has-text('Apply')",
                        "button[aria-label*='Apply']",
                    ]

                    try:
                        self._retry_click(page, show_selectors, "click Show/Apply button")
                        page.wait_for_timeout(2000)
                        logger.info(f"Successfully applied {degree} filter via dropdown")
                        return True
                    except Exception:
                        # Show button might not be needed if clicking the option auto-applies
                        logger.info(f"Show button not found, filter may have auto-applied")
                        page.wait_for_timeout(2000)
                        return True

                except Exception as option_error:
                    logger.error(f"Failed to click {degree} option in dropdown: {option_error}")
                    raise

            except Exception as dropdown_error:
                logger.error(f"Failed to apply {degree} filter via dropdown: {dropdown_error}")
                # Re-raise to signal failure
                raise Exception(f"Failed to click {degree} degree filter after all retries")

    def _clear_connection_filter(self, page):
        """Clear the current connection degree filter by clicking on it again (toggle off)."""
        # Try to find any active filter button and click to deselect
        active_filter_selectors = [
            "button.artdeco-pill--selected:has-text('1st')",
            "button.artdeco-pill--selected:has-text('2nd')",
            "button.artdeco-pill--selected:has-text('3rd')",
            "button[aria-pressed='true']:has-text('1st')",
            "button[aria-pressed='true']:has-text('2nd')",
            "button[aria-pressed='true']:has-text('3rd')",
        ]

        for selector in active_filter_selectors:
            btn = page.query_selector(selector)
            if btn:
                btn.click()
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(1500)
                return

        # If no active filter found, the page may be in a different state - just wait
        page.wait_for_timeout(500)

    def _search_2nd_degree_sync(self, company: str, limit: int) -> list[dict]:
        """
        Synchronous search for 2nd degree connections at a company.
        Follows the user's manual workflow.
        """
        if not HAS_PLAYWRIGHT:
            logger.error("Playwright not installed!")
            return []

        logger.info(f"Starting browser to search for 2nd degree connections at: {company}")
        with sync_playwright() as p:
            try:
                context = p.chromium.launch_persistent_context(
                    str(BROWSER_DATA_PATH),
                    headless=False,  # Use headed mode to avoid detection
                    viewport={"width": 1280, "height": 720},
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(10000)  # 10 second timeout instead of 30
                _apply_stealth(page)

                # Step 1: Go to LinkedIn feed page
                logger.info("Step 1: Going to LinkedIn feed page...")
                page.goto("https://www.linkedin.com/feed/", timeout=60000)
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                _human_delay_medium()

                # Step 2: Find and click the search bar, then type company name
                logger.info(f"Step 2: Searching for '{company}' in search bar...")

                search_selectors = [
                    "input.search-global-typeahead__input",
                    "input[placeholder*='Search']",
                    "input[aria-label*='Search']",
                    ".search-global-typeahead input",
                ]

                search_input = None
                for selector in search_selectors:
                    search_input = page.query_selector(selector)
                    if search_input:
                        logger.info(f"Found search input with selector: {selector}")
                        break

                if not search_input:
                    logger.error("Could not find search bar!")
                    context.close()
                    return []

                search_input.click()
                page.wait_for_timeout(500)
                search_input.fill(company)
                page.wait_for_timeout(500)

                # Press Enter to search
                page.keyboard.press("Enter")
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                # Step 3: Click on "People" tab
                logger.info("Step 3: Clicking on People tab...")

                people_tab_selectors = [
                    "button:has-text('People')",
                    "a:has-text('People')",
                    "[data-test-search-tab='PEOPLE']",
                    ".search-reusables__filter-pill-button:has-text('People')",
                ]

                people_tab = None
                for selector in people_tab_selectors:
                    people_tab = page.query_selector(selector)
                    if people_tab:
                        logger.info(f"Found People tab with selector: {selector}")
                        break

                if not people_tab:
                    logger.error("Could not find People tab!")
                    context.close()
                    return []

                people_tab.click()
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                # Step 4: Filter by 2nd degree connections
                logger.info("Step 4: Filtering by 2nd degree connections...")

                second_degree_selectors = [
                    "button:has-text('2nd')",
                    "button[aria-label*='2nd']",
                    ".search-reusables__filter-pill-button:has-text('2nd')",
                    "li button:has-text('2nd')",
                ]

                second_degree_btn = None
                for selector in second_degree_selectors:
                    second_degree_btn = page.query_selector(selector)
                    if second_degree_btn:
                        logger.info(f"Found 2nd degree filter with selector: {selector}")
                        break

                if second_degree_btn:
                    second_degree_btn.click()
                    page.wait_for_load_state("domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)
                else:
                    # Try clicking "Connections" filter dropdown
                    logger.info("Trying 'Connections' filter dropdown...")
                    connections_filter = page.query_selector("button:has-text('Connections')")
                    if connections_filter:
                        connections_filter.click()
                        page.wait_for_timeout(1000)
                        second_option = page.query_selector("label:has-text('2nd')")
                        if second_option:
                            second_option.click()
                            page.wait_for_timeout(500)
                            show_btn = page.query_selector("button:has-text('Show')")
                            if show_btn:
                                show_btn.click()
                        page.wait_for_timeout(2000)

                # Step 5: Extract people from results (no company filter needed for 2nd degree)
                logger.info("Step 5: Extracting search results...")

                people = self._extract_search_results_2nd_degree(page, company, limit)

                context.close()
                logger.info(f"Found {len(people)} 2nd degree people for {company}")
                return people

            except Exception as e:
                logger.error(f"Search failed: {e}", exc_info=True)
                return []

    def _extract_search_results_2nd_degree(self, page, company: str, limit: int) -> list[dict]:
        """Extract people from search results for 2nd degree connections."""
        people = []
        company_lower = company.lower()

        selectors_to_try = [
            "li.reusable-search__result-container",
            "div.entity-result",
            "[data-view-name='search-entity-result-universal-template']",
            ".search-results-container li",
        ]

        results = []
        for selector in selectors_to_try:
            results = page.query_selector_all(selector)
            if results:
                logger.info(f"Found {len(results)} results using selector: {selector}")
                break

        if not results:
            logger.warning("No search results found with known selectors")
            return []

        for result in results[:limit]:
            try:
                # Get name
                name = ""
                for name_sel in [
                    "span.entity-result__title-text a span[aria-hidden='true']",
                    "span.entity-result__title-text span[aria-hidden='true']",
                    ".entity-result__title-text",
                    "span.t-bold",
                    "a span[aria-hidden='true']",
                ]:
                    name_el = result.query_selector(name_sel)
                    if name_el:
                        name = name_el.inner_text().strip()
                        if name:
                            break

                # Get headline/title
                headline = ""
                for headline_sel in [
                    "div.entity-result__primary-subtitle",
                    ".entity-result__primary-subtitle",
                    "div.t-14.t-normal",
                    ".t-normal",
                ]:
                    headline_el = result.query_selector(headline_sel)
                    if headline_el:
                        headline = headline_el.inner_text().strip()
                        if headline:
                            break

                # For 2nd degree, also verify company in headline
                if company_lower not in headline.lower():
                    logger.debug(f"Skipping {name} - headline doesn't contain company: {headline}")
                    continue

                # Get profile link
                link = ""
                for link_sel in ["a.app-aware-link[href*='/in/']", "a[href*='/in/']"]:
                    link_el = result.query_selector(link_sel)
                    if link_el:
                        link = link_el.get_attribute("href") or ""
                        if "/in/" in link:
                            break

                # Extract public_id from URL
                public_id = ""
                if "/in/" in link:
                    public_id = link.split("/in/")[1].split("/")[0].split("?")[0]

                if name and public_id:
                    people.append({
                        "name": name,
                        "headline": headline,
                        "linkedin_url": f"https://www.linkedin.com/in/{public_id}",
                        "public_id": public_id,
                        "is_connection": False,  # They're 2nd degree - not connections
                    })
                    logger.info(f"Found 2nd degree: {name} - {headline}")

            except Exception as e:
                logger.error(f"Error parsing result: {e}")

        return people

    def _send_connection_requests_on_search_page(self, page, company: str, max_requests: int = 10) -> list[dict]:
        """
        Send connection requests directly from search results page.
        Only clicks "Connect" buttons - skips people with Message/Follow buttons.
        Stops after sending max_requests connection requests.

        Args:
            page: Playwright page object
            company: Company name to match
            max_requests: Maximum number of connection requests to send (default 10)

        Returns list of people who were successfully sent connection requests.
        """
        connected_people = []
        company_lower = company.lower()
        page_num = 0
        max_pages = 5  # Limit to 5 pages of search results

        while len(connected_people) < max_requests and page_num < max_pages:
            page_num += 1
            # Check for abort at start of each page
            self.check_abort()

            logger.info(f"Processing page {page_num} (sent {len(connected_people)}/{max_requests} requests)")

            # Wait for results to load (with abort check)
            self._wait_with_abort_check(page, DELAY_MS)

            # Process current page with remaining request limit
            remaining = max_requests - len(connected_people)
            page_results = self._process_search_results_page(page, company_lower, connected_people, max_to_send=remaining)
            connected_people.extend(page_results)
            logger.info(f"Page {page_num}: sent {len(page_results)} connection requests (total: {len(connected_people)}/{max_requests})")

            # Stop if we've reached our target
            if len(connected_people) >= max_requests:
                logger.info(f"Reached target of {max_requests} connection requests")
                break

            # Go to next page
            if not self._go_to_next_search_page(page):
                logger.info("No more pages available")
                break

        logger.info(f"Sent {len(connected_people)} total connection requests from {page_num} page(s)")
        return connected_people

    def _go_to_next_search_page(self, page) -> bool:
        """Navigate to the next search results page. Returns True if successful."""
        try:
            # First scroll to bottom to ensure pagination is in view
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(500)  # Brief wait after scroll

            # The Next button should already be loaded since we just processed results
            # Try multiple selectors - the button might be rendered differently
            selectors = [
                "button[aria-label='Next']",
                "button:has-text('Next')",
                "a[aria-label='Next']",
                "[aria-label='Next']",
            ]

            next_btn = None
            for selector in selectors:
                next_btn = page.query_selector(selector)
                if next_btn:
                    logger.info(f"Found Next button with selector: {selector}")
                    break

            if next_btn:
                is_enabled = next_btn.is_enabled()
                logger.info(f"Next button found, is_enabled={is_enabled}")
                if is_enabled:
                    logger.info("Clicking Next button to go to next page")
                    next_btn.click()
                    # Wait for new results to load
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    page.wait_for_timeout(DELAY_MS * 2)  # Extra wait for dynamic content
                    return True
                else:
                    logger.info("Next button is disabled - no more pages")
                    return False
            else:
                logger.info("Next button not found on this page")
                return False
        except WorkflowAbortedException:
            raise  # Re-raise abort exception immediately
        except Exception as e:
            logger.error(f"Error navigating to next page: {e}")
            return False

    def _process_search_results_page(self, page, company_lower: str, already_connected: list, max_to_send: int = None) -> list[dict]:
        """Process all results on the current search page.

        Args:
            page: Playwright page object
            company_lower: Lowercase company name to match
            already_connected: List of people already processed
            max_to_send: Maximum number of requests to send on this page (None = unlimited)
        """
        page_connected = []

        # Find all search result items
        selectors_to_try = [
            "li.reusable-search__result-container",
            "div.entity-result",
            "[data-view-name='search-entity-result-universal-template']",
            ".search-results-container li",
        ]

        results = []
        for selector in selectors_to_try:
            results = page.query_selector_all(selector)
            if results:
                logger.info(f"Found {len(results)} results using selector: {selector}")
                break

        if not results:
            logger.warning("No search results found on this page")
            return []

        # Get URLs we've already connected with to avoid duplicates
        already_connected_urls = {p.get("linkedin_url") for p in already_connected}

        for result in results:
            # Check if we've reached our limit
            if max_to_send is not None and len(page_connected) >= max_to_send:
                logger.info(f"Reached max_to_send limit ({max_to_send}) on this page")
                break

            # Check for abort before processing each result
            self.check_abort()

            try:
                # Get person info first
                name = ""
                for name_sel in [
                    "span.entity-result__title-text a span[aria-hidden='true']",
                    "span.entity-result__title-text span[aria-hidden='true']",
                    ".entity-result__title-text",
                    "span.t-bold",
                    "a span[aria-hidden='true']",
                ]:
                    name_el = result.query_selector(name_sel)
                    if name_el:
                        name = name_el.inner_text().strip()
                        if name:
                            break

                # Get headline
                headline = ""
                for headline_sel in [
                    "div.entity-result__primary-subtitle",
                    ".entity-result__primary-subtitle",
                    "div.t-14.t-normal",
                    ".t-normal",
                ]:
                    headline_el = result.query_selector(headline_sel)
                    if headline_el:
                        headline = headline_el.inner_text().strip()
                        if headline:
                            break

                # Check if company name is in headline - skip if not
                if not headline or company_lower not in headline.lower():
                    if name:
                        logger.info(f"Skipping {name} - company '{company_lower}' not in headline: '{headline}'")
                    continue

                # Skip VIPs (CEOs, founders, etc.) - they're too important to cold connect
                headline_lower = headline.lower()
                vip_titles = [
                    'ceo', 'chief executive',
                    'cto', 'chief technology',
                    'cfo', 'chief financial',
                    'coo', 'chief operating',
                    'cmo', 'chief marketing',
                    'cpo', 'chief product',
                    'founder', 'co-founder', 'cofounder',
                    'owner', 'president', 'chairman',
                    'managing director', 'general manager',
                    'vp ', 'vice president',  # Note: space after 'vp' to avoid matching 'vp of recruiting'
                ]
                is_vip = any(title in headline_lower for title in vip_titles)
                if is_vip:
                    logger.info(f"Skipping {name} - VIP title detected in headline: '{headline}'")
                    continue

                # Get profile link
                link = ""
                for link_sel in ["a.app-aware-link[href*='/in/']", "a[href*='/in/']"]:
                    link_el = result.query_selector(link_sel)
                    if link_el:
                        link = link_el.get_attribute("href") or ""
                        if "/in/" in link:
                            break

                public_id = ""
                if "/in/" in link:
                    public_id = link.split("/in/")[1].split("/")[0].split("?")[0]

                if not name or not public_id:
                    continue

                # Skip if already connected to this person
                linkedin_url = f"https://www.linkedin.com/in/{public_id}"
                if linkedin_url in already_connected_urls:
                    logger.debug(f"Skipping {name} - already processed")
                    continue

                # Look for Connect button in this result item (no retry - it's either there or not)
                connect_btn = None
                for selector in ["button:has-text('Connect')", "button[aria-label*='connect']"]:
                    connect_btn = result.query_selector(selector)
                    if connect_btn:
                        break

                if not connect_btn:
                    # No Connect button - person has Message, Follow, or other button
                    logger.info(f"Skipping {name} - no Connect button (has Message/Follow/other)")
                    continue

                # Found Connect button - click it
                logger.info(f"Clicking Connect for: {name}")
                connect_btn.click()
                page.wait_for_timeout(DELAY_MS)

                # Handle the connection modal
                # First check if LinkedIn is asking for email verification (modal with disabled Send)
                page.wait_for_timeout(DELAY_MS // 2)  # Wait for modal to appear

                # Check for email verification modal - "Send without a note" will be disabled
                send_without_note_btn = page.query_selector("button[aria-label='Send without a note'], button:has-text('Send without a note')")
                if send_without_note_btn and not send_without_note_btn.is_enabled():
                    # Email verification required - close modal and skip this person
                    logger.info(f"Skipping {name} - LinkedIn requires email verification to connect")
                    close_btn = page.query_selector("button[aria-label='Dismiss'], button[aria-label='Close']")
                    if close_btn:
                        close_btn.click()
                        page.wait_for_timeout(DELAY_MS // 2)
                    continue  # Don't count this person

                send_btn_selectors = [
                    "button[aria-label='Send without a note']",
                    "button:has-text('Send without a note')",
                    "button[aria-label='Send now']",
                    "button:has-text('Send')",
                ]

                try:
                    self._retry_click(page, send_btn_selectors, f"click Send button for {name}")
                    logger.info(f"Connection request sent to: {name}")

                    page_connected.append({
                        "name": name,
                        "headline": headline,
                        "linkedin_url": linkedin_url,
                        "public_id": public_id,
                        "is_connection": False,
                        "connection_request_sent": True,
                    })
                except WorkflowAbortedException:
                    raise  # Re-raise abort exception immediately
                except Exception as send_error:
                    # Close the modal if we can't send
                    close_btn = page.query_selector("button[aria-label='Dismiss'], button[aria-label='Close']")
                    if close_btn:
                        close_btn.click()
                        page.wait_for_timeout(DELAY_MS // 2)
                    logger.warning(f"Could not send connection to {name}: {send_error}")

                # Small delay between connection requests (with abort check)
                self._wait_with_abort_check(page, DELAY_MS)

            except WorkflowAbortedException:
                raise  # Re-raise abort exception immediately

            except Exception as e:
                logger.error(f"Error sending connection request: {e}")
                # Try to close any open modal
                try:
                    close_btn = page.query_selector("button[aria-label='Dismiss']")
                    if close_btn:
                        close_btn.click()
                        page.wait_for_timeout(DELAY_MS // 2)
                except:
                    pass

        logger.info(f"Sent {len(page_connected)} connection requests on this page")
        return page_connected

    def _send_messages_on_search_page(self, page, company: str, message_generator=None, num_pages: int = 1, first_degree_only: bool = False) -> list[dict]:
        """
        Send messages to 1st degree connections directly from search results page.
        Clicks Message button on each person's card, types message in modal, and sends.

        Args:
            page: Playwright page object
            company: Company name to match
            message_generator: Optional function(name, company) -> str to generate message text.
                              If None, uses a default message.
            num_pages: Number of pages to process (default 1)
            first_degree_only: If True, stop after sending the first successful message

        Returns list of people who were successfully sent messages.
        """
        messaged_people = []
        company_lower = company.lower()

        for page_num in range(1, num_pages + 1):
            # Check for abort at start of each page
            self.check_abort()

            logger.info(f"Processing page {page_num} of {num_pages} for messaging")

            # Wait for results to load (with abort check)
            self._wait_with_abort_check(page, DELAY_MS)

            # Process current page
            page_results = self._process_message_results_page(page, company_lower, already_messaged=messaged_people, message_generator=message_generator, first_degree_only=first_degree_only)
            messaged_people.extend(page_results)
            logger.info(f"Page {page_num}: sent {len(page_results)} messages (total: {len(messaged_people)})")

            # If first_degree_only and we sent a message, stop (only message one person)
            if first_degree_only and len(messaged_people) > 0:
                logger.info("First degree only mode: Stopping after first successful message")
                break

            # Go to next page if not on last page
            if page_num < num_pages:
                if not self._go_to_next_search_page(page):
                    logger.info("No more pages available")
                    break

        logger.info(f"Sent {len(messaged_people)} total messages from {page_num} page(s)")
        return messaged_people

    def _process_message_results_page(self, page, company_lower: str, already_messaged: list, message_generator=None, first_degree_only: bool = False) -> list[dict]:
        """Process all results on the current search page to send messages."""
        page_messaged = []

        # Find all search result items
        selectors_to_try = [
            "li.reusable-search__result-container",
            "div.entity-result",
            "[data-view-name='search-entity-result-universal-template']",
            ".search-results-container li",
        ]

        results = []
        for selector in selectors_to_try:
            results = page.query_selector_all(selector)
            if results:
                logger.info(f"Found {len(results)} results for messaging using selector: {selector}")
                break

        if not results:
            logger.warning("No search results found on this page for messaging")
            return []

        # Get URLs we've already messaged to avoid duplicates
        already_messaged_urls = {p.get("linkedin_url") for p in already_messaged}

        for result in results:
            # Check for abort before processing each result
            self.check_abort()

            try:
                # Get person info first
                name = ""
                for name_sel in [
                    "span.entity-result__title-text a span[aria-hidden='true']",
                    "span.entity-result__title-text span[aria-hidden='true']",
                    ".entity-result__title-text",
                    "span.t-bold",
                    "a span[aria-hidden='true']",
                ]:
                    name_el = result.query_selector(name_sel)
                    if name_el:
                        name = name_el.inner_text().strip()
                        if name:
                            break

                # Get headline
                headline = ""
                for headline_sel in [
                    "div.entity-result__primary-subtitle",
                    ".entity-result__primary-subtitle",
                    "div.t-14.t-normal",
                    ".t-normal",
                ]:
                    headline_el = result.query_selector(headline_sel)
                    if headline_el:
                        headline = headline_el.inner_text().strip()
                        if headline:
                            break

                # Check if company name is in headline - skip if not
                if not headline or company_lower not in headline.lower():
                    if name:
                        logger.info(f"Skipping {name} for messaging - company not in headline: '{headline}'")
                    continue

                # Skip VIPs (CEOs, founders, etc.) - they're too important to cold message
                headline_lower = headline.lower()
                vip_titles = [
                    'ceo', 'chief executive',
                    'cto', 'chief technology',
                    'cfo', 'chief financial',
                    'coo', 'chief operating',
                    'cmo', 'chief marketing',
                    'cpo', 'chief product',
                    'founder', 'co-founder', 'cofounder',
                    'owner', 'president', 'chairman',
                    'managing director', 'general manager',
                    'vp ', 'vice president',  # Note: space after 'vp' to avoid matching 'vp of recruiting'
                ]
                is_vip = any(title in headline_lower for title in vip_titles)
                if is_vip:
                    logger.info(f"Skipping {name} - VIP title detected in headline: '{headline}'")
                    continue

                # Get profile link
                link = ""
                for link_sel in ["a.app-aware-link[href*='/in/']", "a[href*='/in/']"]:
                    link_el = result.query_selector(link_sel)
                    if link_el:
                        link = link_el.get_attribute("href") or ""
                        if "/in/" in link:
                            break

                public_id = ""
                if "/in/" in link:
                    public_id = link.split("/in/")[1].split("/")[0].split("?")[0]

                if not name or not public_id:
                    continue

                # Skip if already messaged this person
                linkedin_url = f"https://www.linkedin.com/in/{public_id}"
                if linkedin_url in already_messaged_urls:
                    logger.debug(f"Skipping {name} - already messaged")
                    continue

                # Look for Message button in this result item with retry
                message_btn_selectors = [
                    "button:has-text('Message')",
                    "button[aria-label*='Message']",
                ]
                message_btn = self._retry_find_in_element(page, result, message_btn_selectors, f"find Message button for {name}")

                if not message_btn:
                    logger.info(f"Skipping {name} - no Message button (not a 1st degree connection)")
                    continue

                # Found Message button - click it
                logger.info(f"Clicking Message for: {name}")
                message_btn.click()
                page.wait_for_timeout(DELAY_MS * 2)  # Wait for modal to open

                # Verify the chat modal actually opened
                modal_opened = page.evaluate("""
                    () => {
                        return !!(document.querySelector('[role="dialog"]') ||
                                  document.querySelector('.msg-overlay-conversation-bubble'));
                    }
                """)
                if not modal_opened:
                    logger.warning(f"Chat modal didn't open for {name}, skipping")
                    continue

                # Check if there's existing message history in the chat
                # If we've messaged this person before or they messaged us, skip them
                has_existing_history = False
                try:
                    # Use JavaScript to check for ACTUAL message history in the chat modal
                    # Returns {count, texts} for debugging
                    # Wait a moment for chat content to load
                    page.wait_for_timeout(500)

                    history_result = page.evaluate("""
                        () => {
                            const result = { count: 0, texts: [], method: '', debug: {} };

                            // Debug: Check what dialogs exist
                            const roleDialog = document.querySelector('[role="dialog"]');
                            const overlayBubble = document.querySelector('.msg-overlay-conversation-bubble');
                            result.debug.hasRoleDialog = !!roleDialog;
                            result.debug.hasOverlayBubble = !!overlayBubble;
                            result.debug.roleDialogClasses = roleDialog ? roleDialog.className : 'N/A';
                            result.debug.overlayBubbleClasses = overlayBubble ? overlayBubble.className : 'N/A';

                            // Find the messaging dialog
                            const dialog = roleDialog || overlayBubble;
                            if (!dialog) {
                                result.count = -1;
                                result.method = 'no dialog';
                                result.debug.allDialogs = Array.from(document.querySelectorAll('dialog, [role="dialog"]')).map(d => d.className).join(', ');
                                return result;
                            }

                            // Debug: Check all potential message containers in the dialog
                            result.debug.msgBodiesCount = dialog.querySelectorAll('.msg-s-event-listitem__body').length;
                            result.debug.msgBubblesCount = dialog.querySelectorAll('.msg-s-message-group__bubble').length;
                            result.debug.msgListContent = !!dialog.querySelector('ul.msg-s-message-list-content');
                            result.debug.msgListOld = !!dialog.querySelector('ul.msg-s-message-list');
                            result.debug.anyUlCount = dialog.querySelectorAll('ul').length;
                            result.debug.anyLiCount = dialog.querySelectorAll('li').length;

                            // Debug: Get first 3 class names of li elements to understand structure
                            const lis = dialog.querySelectorAll('li');
                            result.debug.liClasses = Array.from(lis).slice(0, 5).map(li => li.className.substring(0, 80));

                            // Primary method: Look for message body elements directly
                            // This is the most reliable selector for actual message content
                            const messageBodies = dialog.querySelectorAll('.msg-s-event-listitem__body');
                            if (messageBodies.length > 0) {
                                result.method = 'bodies';
                                messageBodies.forEach(body => {
                                    const text = body.textContent.trim();
                                    const textLower = text.toLowerCase();
                                    // Skip system messages and deleted messages
                                    if (textLower.includes('accepted your invitation') ||
                                        textLower.includes('you are now connected') ||
                                        textLower.includes('sent you a connection request') ||
                                        textLower.includes('wants to connect') ||
                                        textLower.includes('connection request') ||
                                        textLower.includes('this message has been deleted')) {
                                        result.texts.push('[SYSTEM] ' + text.substring(0, 50));
                                        return;
                                    }
                                    result.count++;
                                    result.texts.push(text.substring(0, 50));
                                });
                                return result;
                            }

                            // Fallback: Look for message bubbles (older LinkedIn structure)
                            const messageBubbles = dialog.querySelectorAll(
                                '.msg-s-message-group__bubble'
                            );

                            if (messageBubbles.length > 0) {
                                result.method = 'bubbles';
                                messageBubbles.forEach(bubble => {
                                    const text = bubble.textContent.trim();
                                    const textLower = text.toLowerCase();
                                    // Skip system messages only
                                    if (textLower.includes('accepted your invitation') ||
                                        textLower.includes('you are now connected') ||
                                        textLower.includes('sent you a connection request') ||
                                        textLower.includes('wants to connect') ||
                                        textLower.includes('connection request')) {
                                        result.texts.push('[SYSTEM] ' + text.substring(0, 50));
                                        return;
                                    }
                                    result.count++;
                                    result.texts.push(text.substring(0, 50));
                                });
                                return result;
                            }

                            // Fallback: Look for message list items with actual content
                            // Note: LinkedIn changed from 'ul.msg-s-message-list' to 'ul.msg-s-message-list-content'
                            const messageList = dialog.querySelector('ul.msg-s-message-list-content') || dialog.querySelector('ul.msg-s-message-list');
                            if (!messageList) {
                                result.count = -2;
                                result.method = 'no list';
                                // Extra debug: dump all UL classes in dialog
                                result.debug.allUlClasses = Array.from(dialog.querySelectorAll('ul')).map(ul => ul.className.substring(0, 60));
                                return result;
                            }

                            result.method = 'events';
                            const messageEvents = messageList.querySelectorAll('li.msg-s-message-list__event');

                            messageEvents.forEach(event => {
                                const messageBody = event.querySelector('.msg-s-event-listitem__body');
                                if (messageBody) {
                                    const text = messageBody.textContent.trim();
                                    const textLower = text.toLowerCase();
                                    // Skip system messages only
                                    if (textLower.includes('accepted your invitation') ||
                                        textLower.includes('you are now connected') ||
                                        textLower.includes('connection request')) {
                                        result.texts.push('[SYSTEM] ' + text.substring(0, 50));
                                        return;
                                    }
                                    result.count++;
                                    result.texts.push(text.substring(0, 50));
                                }
                            });

                            return result;
                        }
                    """)

                    message_count = history_result.get('count', 0)
                    detected_texts = history_result.get('texts', [])
                    method_used = history_result.get('method', 'unknown')
                    debug_info = history_result.get('debug', {})

                    logger.info(f"Message history check for {name}: found {message_count} messages (method: {method_used})")
                    logger.info(f"DEBUG info: {debug_info}")
                    if detected_texts:
                        logger.info(f"Detected texts: {detected_texts}")

                    # If we got -2 (no list), this might be a timing issue - retry after more wait
                    if message_count == -2:
                        logger.warning(f"DETECTION FAILED for {name}: Could not find message list. Debug: {debug_info}")
                        logger.info(f"Retrying detection for {name} after additional wait...")
                        page.wait_for_timeout(1000)  # Wait 1 more second

                        # Retry the detection
                        retry_result = page.evaluate("""
                            () => {
                                const result = { count: 0, texts: [], method: '', debug: {} };
                                const dialog = document.querySelector('[role="dialog"]') || document.querySelector('.msg-overlay-conversation-bubble');
                                if (!dialog) {
                                    result.count = -1;
                                    result.method = 'no dialog (retry)';
                                    return result;
                                }

                                result.debug.msgBodiesCount = dialog.querySelectorAll('.msg-s-event-listitem__body').length;
                                result.debug.anyUlCount = dialog.querySelectorAll('ul').length;
                                result.debug.anyLiCount = dialog.querySelectorAll('li').length;

                                const messageBodies = dialog.querySelectorAll('.msg-s-event-listitem__body');
                                if (messageBodies.length > 0) {
                                    result.method = 'bodies (retry)';
                                    messageBodies.forEach(body => {
                                        const text = body.textContent.trim();
                                        const textLower = text.toLowerCase();
                                        if (textLower.includes('accepted your invitation') ||
                                            textLower.includes('you are now connected') ||
                                            textLower.includes('sent you a connection request') ||
                                            textLower.includes('wants to connect') ||
                                            textLower.includes('connection request') ||
                                            textLower.includes('this message has been deleted')) {
                                            result.texts.push('[SYSTEM] ' + text.substring(0, 50));
                                            return;
                                        }
                                        result.count++;
                                        result.texts.push(text.substring(0, 50));
                                    });
                                    return result;
                                }

                                // Still no bodies, check for any list
                                const messageList = dialog.querySelector('ul.msg-s-message-list-content') || dialog.querySelector('ul.msg-s-message-list');
                                if (!messageList) {
                                    result.count = -2;
                                    result.method = 'no list (retry)';
                                    result.debug.allUlClasses = Array.from(dialog.querySelectorAll('ul')).map(ul => ul.className.substring(0, 60));
                                    return result;
                                }

                                return result;
                            }
                        """)

                        message_count = retry_result.get('count', 0)
                        detected_texts = retry_result.get('texts', [])
                        method_used = retry_result.get('method', 'unknown')
                        debug_info = retry_result.get('debug', {})
                        logger.info(f"RETRY result for {name}: found {message_count} messages (method: {method_used})")
                        logger.info(f"RETRY DEBUG info: {debug_info}")
                        if detected_texts:
                            logger.info(f"RETRY Detected texts: {detected_texts}")

                    if message_count > 0:
                        has_existing_history = True
                        logger.info(f"Existing conversation detected with {name} ({message_count} messages) - skipping")

                    if has_existing_history:
                        # Close the chat modal and skip to next person
                        # Try multiple methods to close the chat
                        closed = page.evaluate("""
                            () => {
                                let closed = false;

                                // Method 1: Find close button by aria-label in conversation bubble
                                const closeButtons = document.querySelectorAll(
                                    '.msg-overlay-conversation-bubble button[aria-label*="Close"], ' +
                                    '.msg-overlay-bubble-header button[aria-label*="Close"], ' +
                                    '[role="dialog"] button[aria-label*="Close"]'
                                );
                                for (const btn of closeButtons) {
                                    try {
                                        btn.click();
                                        closed = true;
                                        break;
                                    } catch (e) {}
                                }

                                // Method 2: Try header control buttons (X button)
                                if (!closed) {
                                    const headerControls = document.querySelectorAll(
                                        '.msg-overlay-bubble-header__control, ' +
                                        '.msg-overlay-conversation-bubble__close-btn'
                                    );
                                    for (const ctrl of headerControls) {
                                        // Skip expand/new convo buttons
                                        if (ctrl.classList.contains('msg-overlay-conversation-bubble__expand-btn') ||
                                            ctrl.classList.contains('msg-overlay-bubble-header__control--new-convo-btn')) {
                                            continue;
                                        }
                                        try {
                                            ctrl.click();
                                            closed = true;
                                            break;
                                        } catch (e) {}
                                    }
                                }

                                // Method 3: Press Escape key to close modal
                                if (!closed) {
                                    document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', keyCode: 27, bubbles: true}));
                                    closed = true;  // Assume it worked
                                }

                                return closed;
                            }
                        """)
                        logger.info(f"Closed chat modal for {name}: {closed}")

                        # Extra wait and verify it's closed
                        page.wait_for_timeout(500)

                        # Double-check: if still open, try pressing Escape via Playwright
                        still_open = page.evaluate("""
                            () => {
                                return !!document.querySelector('.msg-overlay-conversation-bubble, [role="dialog"]');
                            }
                        """)
                        if still_open:
                            logger.info(f"Chat still open after JS close, pressing Escape")
                            page.keyboard.press("Escape")
                            page.wait_for_timeout(300)

                        continue  # Skip to next person in the loop

                except WorkflowAbortedException:
                    raise  # Re-raise abort exception immediately
                except Exception as history_check_error:
                    logger.warning(f"Could not check message history for {name}: {history_check_error}")
                    # Continue with sending message if check fails

                # Find message input with retry
                message_input_selectors = [
                    "div.msg-form__contenteditable",
                    "[contenteditable='true']",
                    "div[role='textbox']",
                    ".msg-form__msg-content-container div[contenteditable]",
                ]

                try:
                    message_input = self._retry_find(page, message_input_selectors, f"find message input for {name}")

                    # Generate message using provided generator or default
                    first_name = name.split()[0] if name else "there"
                    if message_generator:
                        try:
                            message_text = message_generator(name, company_lower)
                        except MissingHebrewNamesException as e:
                            # Hebrew name translation missing - close chat and record
                            logger.info(f"Missing Hebrew translation for {name}, closing chat and recording")
                            # Close the chat modal
                            page.evaluate("""
                                () => {
                                    const closeButtons = document.querySelectorAll(
                                        '.msg-overlay-conversation-bubble button[aria-label*="Close"], ' +
                                        '.msg-overlay-bubble-header button[aria-label*="Close"], ' +
                                        '[role="dialog"] button[aria-label*="Close"]'
                                    );
                                    for (const btn of closeButtons) {
                                        try { btn.click(); break; } catch (e) {}
                                    }
                                }
                            """)
                            page.wait_for_timeout(300)
                            page.keyboard.press("Escape")
                            page.wait_for_timeout(300)
                            # Re-raise to be caught by outer handler
                            raise
                    else:
                        message_text = f"Hi {first_name}, I noticed you work at {company_lower}. I'd love to connect about an opportunity there!"

                    # Click and type
                    message_input.click()
                    page.wait_for_timeout(300)
                    message_input.fill(message_text)
                    page.wait_for_timeout(500)

                    # Click send button with retry
                    send_btn_selectors = [
                        "button.msg-form__send-button",
                        "button[type='submit']",
                        "button:has-text('Send')",
                        "button[aria-label='Send']",
                    ]

                    try:
                        self._retry_click(page, send_btn_selectors, f"click Send button for {name}")
                        logger.info(f"Message sent to: {name}")

                        page_messaged.append({
                            "name": name,
                            "headline": headline,
                            "linkedin_url": linkedin_url,
                            "public_id": public_id,
                            "is_connection": True,
                            "message_sent": True,
                        })

                        # Close the chat modal after sending
                        page.wait_for_timeout(500)  # Wait for message to be sent
                        page.evaluate("""
                            () => {
                                const closeButtons = document.querySelectorAll(
                                    '.msg-overlay-conversation-bubble button[aria-label*="Close"], ' +
                                    '.msg-overlay-bubble-header button[aria-label*="Close"], ' +
                                    '[role="dialog"] button[aria-label*="Close"]'
                                );
                                for (const btn of closeButtons) {
                                    try { btn.click(); break; } catch (e) {}
                                }
                            }
                        """)
                        page.wait_for_timeout(500)  # Wait for modal to fully close

                        # Always stop after first successful message - workflow is: message ONE person, then wait for reply
                        logger.info("Message sent successfully - stopping to wait for reply")
                        return page_messaged

                    except (WorkflowAbortedException, MissingHebrewNamesException):
                        raise  # Re-raise these exceptions immediately
                    except Exception as send_error:
                        logger.warning(f"Could not find Send button for {name}: {send_error}")
                        # Close the modal
                        close_btn = page.query_selector("button[aria-label='Dismiss']")
                        if close_btn:
                            close_btn.click()
                            page.wait_for_timeout(300)

                except (WorkflowAbortedException, MissingHebrewNamesException):
                    raise  # Re-raise these exceptions immediately
                except Exception as input_error:
                    logger.warning(f"Could not find message input for {name}: {input_error}")
                    # Close the modal
                    close_btn = page.query_selector("button[aria-label='Dismiss']")
                    if not close_btn:
                        close_btn = page.query_selector("button.msg-overlay-bubble-header__control--close")
                    if close_btn:
                        close_btn.click()
                        page.wait_for_timeout(300)

                # Small delay between messages (with abort check)
                self._wait_with_abort_check(page, DELAY_MS)

            except (WorkflowAbortedException, MissingHebrewNamesException):
                raise  # Re-raise these exceptions immediately

            except Exception as e:
                logger.error(f"Error sending message: {e}")
                # Try to close any open modal
                try:
                    close_btn = page.query_selector("button[aria-label='Dismiss']")
                    if close_btn:
                        close_btn.click()
                        page.wait_for_timeout(300)
                except:
                    pass

        logger.info(f"Sent {len(page_messaged)} messages on this page")
        return page_messaged

    async def get_connections(self, limit: int = 100) -> list[dict]:
        """Get the user's connections."""
        if not self._logged_in:
            logger.error("Not logged in")
            return []

        return await _run_playwright_async(self._get_connections_sync, limit)

    def _get_connections_sync(self, limit: int) -> list[dict]:
        """Synchronous get connections using browser."""
        if not HAS_PLAYWRIGHT:
            logger.error("Playwright not installed!")
            return []

        logger.info("Starting browser to get connections...")
        with sync_playwright() as p:
            try:
                logger.info(f"Launching persistent browser context from: {BROWSER_DATA_PATH}")
                context = p.chromium.launch_persistent_context(
                    str(BROWSER_DATA_PATH),
                    headless=False,  # Use headed mode to avoid detection
                    viewport={"width": 1280, "height": 720},
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(10000)  # 10 second timeout instead of 30
                _apply_stealth(page)
                logger.info("Browser launched, navigating to connections page...")

                # Go to connections page
                page.goto("https://www.linkedin.com/mynetwork/invite-connect/connections/", timeout=60000)
                logger.info("Page loaded, waiting for DOM...")
                # Use domcontentloaded instead of networkidle (faster, more reliable)
                page.wait_for_load_state("domcontentloaded", timeout=30000)

                # Wait a bit for dynamic content to load
                logger.info("DOM loaded, waiting for dynamic content...")
                _human_delay_long()

                connections = []

                # Try multiple selectors as LinkedIn changes their UI
                selectors_to_try = [
                    "li.mn-connection-card",
                    "div.mn-connection-card",
                    "[data-view-name='connections-list-item']",
                    ".scaffold-finite-scroll__content > li",
                ]

                results = []
                for selector in selectors_to_try:
                    results = page.query_selector_all(selector)
                    if results:
                        logger.info(f"Found {len(results)} connections using selector: {selector}")
                        break

                if not results:
                    # Try to find any list items in the connections area
                    logger.warning("Could not find connections with known selectors, trying generic approach")
                    results = page.query_selector_all("main li")
                    logger.info(f"Found {len(results)} generic list items")

                for result in results[:limit]:
                    try:
                        # Try multiple name selectors
                        name = ""
                        for name_sel in ["span.mn-connection-card__name", ".entity-result__title-text", "a span[aria-hidden='true']", "span.t-bold"]:
                            name_el = result.query_selector(name_sel)
                            if name_el:
                                name = name_el.inner_text().strip()
                                break

                        # Try multiple headline selectors
                        headline = ""
                        for headline_sel in ["span.mn-connection-card__occupation", ".entity-result__primary-subtitle", ".t-normal"]:
                            headline_el = result.query_selector(headline_sel)
                            if headline_el:
                                headline = headline_el.inner_text().strip()
                                break

                        # Try to find link
                        link = ""
                        for link_sel in ["a.mn-connection-card__link", "a[href*='/in/']"]:
                            link_el = result.query_selector(link_sel)
                            if link_el:
                                link = link_el.get_attribute("href") or ""
                                break

                        public_id = ""
                        if "/in/" in link:
                            public_id = link.split("/in/")[1].split("/")[0].split("?")[0]

                        if name and public_id:  # Only add if we got valid data
                            connections.append({
                                "name": name,
                                "headline": headline,
                                "linkedin_url": f"https://www.linkedin.com/in/{public_id}",
                                "public_id": public_id,
                                "is_connection": True,
                            })
                    except Exception as e:
                        logger.error(f"Error parsing connection: {e}")

                context.close()
                logger.info(f"Retrieved {len(connections)} connections")
                return connections

            except Exception as e:
                logger.error(f"Failed to get connections: {e}", exc_info=True)
                return []

    async def search_connections_by_company(self, company: str) -> list[dict]:
        """
        Search for people at a company using the user's workflow:
        1. Go to feed page
        2. Use search bar to search company name
        3. Click People tab
        4. Filter by 1st degree connections
        5. Return people whose title contains company name
        """
        logger.info(f"Searching for 1st degree connections at: {company}")

        if not self._logged_in:
            logger.error("Not logged in")
            return []

        return await _run_playwright_async(self._search_company_connections_sync, company)

    def _search_company_connections_sync(self, company: str) -> list[dict]:
        """
        Synchronous search for 1st degree connections at a company.
        Follows the user's manual workflow exactly.
        """
        if not HAS_PLAYWRIGHT:
            logger.error("Playwright not installed!")
            return []

        logger.info(f"Starting browser to search for connections at: {company}")
        with sync_playwright() as p:
            try:
                context = p.chromium.launch_persistent_context(
                    str(BROWSER_DATA_PATH),
                    headless=False,  # Use headed mode to avoid detection
                    viewport={"width": 1280, "height": 720},
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(10000)  # 10 second timeout instead of 30
                _apply_stealth(page)

                # Step 1: Go to LinkedIn feed page
                logger.info("Step 1: Going to LinkedIn feed page...")
                page.goto("https://www.linkedin.com/feed/", timeout=60000)
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                _human_delay_medium()

                # Step 2: Find and click the search bar, then type company name
                logger.info(f"Step 2: Searching for '{company}' in search bar...")

                # Try different selectors for the search input
                search_selectors = [
                    "input.search-global-typeahead__input",
                    "input[placeholder*='Search']",
                    "input[aria-label*='Search']",
                    ".search-global-typeahead input",
                ]

                search_input = None
                for selector in search_selectors:
                    search_input = page.query_selector(selector)
                    if search_input:
                        logger.info(f"Found search input with selector: {selector}")
                        break

                if not search_input:
                    logger.error("Could not find search bar!")
                    context.close()
                    return []

                # Click and type in search bar
                search_input.click()
                page.wait_for_timeout(500)
                search_input.fill(company)
                page.wait_for_timeout(500)

                # Press Enter to search
                page.keyboard.press("Enter")
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                # Step 3: Click on "People" tab
                logger.info("Step 3: Clicking on People tab...")

                people_tab_selectors = [
                    "button:has-text('People')",
                    "a:has-text('People')",
                    "[data-test-search-tab='PEOPLE']",
                    ".search-reusables__filter-pill-button:has-text('People')",
                ]

                people_tab = None
                for selector in people_tab_selectors:
                    people_tab = page.query_selector(selector)
                    if people_tab:
                        logger.info(f"Found People tab with selector: {selector}")
                        break

                if not people_tab:
                    logger.error("Could not find People tab!")
                    context.close()
                    return []

                people_tab.click()
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                # Step 4: Filter by 1st degree connections
                logger.info("Step 4: Filtering by 1st degree connections...")

                # Try to find the connection degree filter
                first_degree_selectors = [
                    "button:has-text('1st')",
                    "button[aria-label*='1st']",
                    ".search-reusables__filter-pill-button:has-text('1st')",
                    "li button:has-text('1st')",
                ]

                first_degree_btn = None
                for selector in first_degree_selectors:
                    first_degree_btn = page.query_selector(selector)
                    if first_degree_btn:
                        logger.info(f"Found 1st degree filter with selector: {selector}")
                        break

                if first_degree_btn:
                    first_degree_btn.click()
                    page.wait_for_load_state("domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)
                else:
                    # Try clicking "All filters" and selecting from there
                    logger.info("Trying 'Connections' filter dropdown...")
                    connections_filter = page.query_selector("button:has-text('Connections')")
                    if connections_filter:
                        connections_filter.click()
                        page.wait_for_timeout(1000)
                        first_option = page.query_selector("label:has-text('1st')")
                        if first_option:
                            first_option.click()
                            page.wait_for_timeout(500)
                            # Click "Show results" or similar
                            show_btn = page.query_selector("button:has-text('Show')")
                            if show_btn:
                                show_btn.click()
                        page.wait_for_timeout(2000)

                # Step 5: Extract people from results
                logger.info("Step 5: Extracting search results...")

                people = self._extract_search_results(page, company)

                context.close()
                logger.info(f"Found {len(people)} 1st degree connections at {company}")
                return people

            except Exception as e:
                logger.error(f"Search failed: {e}", exc_info=True)
                return []

    def _extract_search_results(self, page, company: str) -> list[dict]:
        """Extract people from search results page and filter by company in title."""
        people = []
        company_lower = company.lower()

        # Try multiple selectors for search results
        selectors_to_try = [
            "li.reusable-search__result-container",
            "div.entity-result",
            "[data-view-name='search-entity-result-universal-template']",
            ".search-results-container li",
        ]

        results = []
        for selector in selectors_to_try:
            results = page.query_selector_all(selector)
            if results:
                logger.info(f"Found {len(results)} results using selector: {selector}")
                break

        if not results:
            logger.warning("No search results found with known selectors")
            return []

        for result in results:
            try:
                # Get name
                name = ""
                for name_sel in [
                    "span.entity-result__title-text a span[aria-hidden='true']",
                    "span.entity-result__title-text span[aria-hidden='true']",
                    ".entity-result__title-text",
                    "span.t-bold",
                    "a span[aria-hidden='true']",
                ]:
                    name_el = result.query_selector(name_sel)
                    if name_el:
                        name = name_el.inner_text().strip()
                        if name:
                            break

                # Get headline/title
                headline = ""
                for headline_sel in [
                    "div.entity-result__primary-subtitle",
                    ".entity-result__primary-subtitle",
                    "div.t-14.t-normal",
                    ".t-normal",
                ]:
                    headline_el = result.query_selector(headline_sel)
                    if headline_el:
                        headline = headline_el.inner_text().strip()
                        if headline:
                            break

                # Verify the person actually works at the company (check headline)
                if company_lower not in headline.lower():
                    logger.debug(f"Skipping {name} - headline doesn't contain company: {headline}")
                    continue

                # Get profile link
                link = ""
                for link_sel in ["a.app-aware-link[href*='/in/']", "a[href*='/in/']"]:
                    link_el = result.query_selector(link_sel)
                    if link_el:
                        link = link_el.get_attribute("href") or ""
                        if "/in/" in link:
                            break

                # Extract public_id from URL
                public_id = ""
                if "/in/" in link:
                    public_id = link.split("/in/")[1].split("/")[0].split("?")[0]

                if name and public_id:
                    people.append({
                        "name": name,
                        "headline": headline,
                        "linkedin_url": f"https://www.linkedin.com/in/{public_id}",
                        "public_id": public_id,
                        "is_connection": True,  # They're 1st degree connections
                    })
                    logger.info(f"Found connection: {name} - {headline}")

            except Exception as e:
                logger.error(f"Error parsing result: {e}")

        return people

    async def send_message(
        self,
        message: str,
        public_id: str = None,
        profile_url: str = None,
        urn_id: str = None,  # Not used but accepted for compatibility
    ) -> bool:
        """Send a message to a connection.

        Args:
            message: The message text to send
            public_id: LinkedIn public ID (e.g., 'john-doe')
            profile_url: Full LinkedIn profile URL (e.g., 'https://linkedin.com/in/john-doe')
            urn_id: LinkedIn URN ID (not used, for API compatibility)
        """
        if not self._logged_in:
            logger.error("Not logged in")
            return False

        # Extract public_id from profile_url if not provided
        if not public_id and profile_url:
            if "/in/" in profile_url:
                public_id = profile_url.split("/in/")[1].rstrip("/").split("?")[0]

        if not public_id:
            logger.error("No public_id or profile_url provided for send_message")
            return False

        return await _run_playwright_async(self._send_message_sync, public_id, message)

    def _send_message_sync(self, public_id: str, message: str) -> bool:
        """Synchronous send message using browser."""
        if not HAS_PLAYWRIGHT:
            return False

        with sync_playwright() as p:
            try:
                context = p.chromium.launch_persistent_context(
                    str(BROWSER_DATA_PATH),
                    headless=False,  # Visible for messaging (safer)
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(10000)  # 10 second timeout instead of 30
                _apply_stealth(page)

                # Go to the person's profile
                page.goto(f"https://www.linkedin.com/in/{public_id}/")
                page.wait_for_load_state("networkidle")
                _human_delay_medium()

                # Click Message button
                message_btn = page.query_selector("button:has-text('Message')")
                if not message_btn:
                    logger.error("Message button not found - may not be a connection")
                    context.close()
                    return False

                message_btn.click()
                page.wait_for_timeout(1000)

                # Type message in the modal
                message_input = page.query_selector("div.msg-form__contenteditable")
                if message_input:
                    message_input.fill(message)
                    page.wait_for_timeout(500)

                    # Click send
                    send_btn = page.query_selector("button.msg-form__send-button")
                    if send_btn:
                        send_btn.click()
                        page.wait_for_timeout(2000)
                        logger.info(f"Message sent to {public_id}")
                        context.close()
                        return True

                context.close()
                return False

            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                return False

    async def send_connection_request(
        self,
        public_id: str,
        message: str = None,
    ) -> bool:
        """Send a connection request."""
        if not self._logged_in:
            logger.error("Not logged in")
            return False

        return await _run_playwright_async(self._send_connection_request_sync, public_id, message)

    def _send_connection_request_sync(self, public_id: str, message: str = None) -> bool:
        """Synchronous send connection request using browser."""
        if not HAS_PLAYWRIGHT:
            return False

        with sync_playwright() as p:
            try:
                context = p.chromium.launch_persistent_context(
                    str(BROWSER_DATA_PATH),
                    headless=False,  # Visible for connection requests (safer)
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(10000)  # 10 second timeout instead of 30
                _apply_stealth(page)

                # Go to the person's profile
                page.goto(f"https://www.linkedin.com/in/{public_id}/")
                page.wait_for_load_state("networkidle")
                _human_delay_medium()

                # Click Connect button
                connect_btn = page.query_selector("button:has-text('Connect')")
                if not connect_btn:
                    logger.error("Connect button not found")
                    context.close()
                    return False

                connect_btn.click()
                page.wait_for_timeout(1000)

                # If there's a modal asking how you know them
                add_note_btn = page.query_selector("button:has-text('Add a note')")
                if add_note_btn and message:
                    add_note_btn.click()
                    page.wait_for_timeout(500)

                    # Type the note
                    note_input = page.query_selector("textarea#custom-message")
                    if note_input:
                        note_input.fill(message[:300])  # Max 300 chars
                        page.wait_for_timeout(500)

                # Click Send
                send_btn = page.query_selector("button:has-text('Send')")
                if send_btn:
                    send_btn.click()
                    page.wait_for_timeout(2000)
                    logger.info(f"Connection request sent to {public_id}")
                    context.close()
                    return True

                context.close()
                return False

            except Exception as e:
                logger.error(f"Failed to send connection request: {e}")
                return False

    async def check_for_replies(self, contacts: list[dict], company: str) -> list[dict]:
        """
        Check if any of the contacts we messaged have replied.

        Args:
            contacts: List of contact dicts with 'name', 'linkedin_url', 'public_id'
            company: Company name for context

        Returns:
            List of contacts who have replied
        """
        if not self._logged_in:
            logger.error("Not logged in")
            return []

        if not contacts:
            logger.info("No contacts to check for replies")
            return []

        return await _run_playwright_async(self._check_for_replies_sync, contacts, company)

    def _check_for_replies_sync(self, contacts: list[dict], company: str) -> list[dict]:
        """Synchronous version of check_for_replies."""
        if not HAS_PLAYWRIGHT:
            return []

        replied_contacts = []

        with sync_playwright() as p:
            context = None
            try:
                context = p.chromium.launch_persistent_context(
                    str(BROWSER_DATA_PATH),
                    headless=False,
                    viewport={"width": 1280, "height": 720},
                    args=["--window-size=1300,750", "--window-position=100,100"],
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(10000)  # 10 second timeout instead of 30
                _apply_stealth(page)

                # Go to LinkedIn feed (any page with the navbar)
                logger.info("Going to LinkedIn feed to access messaging...")
                page.goto("https://www.linkedin.com/feed/", timeout=60000)
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                _human_delay_medium()
                page.wait_for_timeout(DELAY_MS)

                # Close any open message overlays before starting
                self._close_all_message_overlays(page)

                # Click the floating "Messaging" button at bottom right to open the messaging panel
                # This is NOT the navbar link - it's a floating chat-style button
                logger.info("Looking for floating Messaging button at bottom right...")

                # First, check if the messaging panel is already open/expanded
                # The panel is open if we can see the conversations list or search input
                panel_open_selectors = [
                    ".msg-overlay-list-bubble--is-open",
                    ".msg-overlay-list-bubble__conversations-container",
                    ".msg-conversations-container",
                    ".msg-overlay-list-bubble input[placeholder*='Search']",
                    ".msg-search-form input",
                ]

                panel_already_open = False
                for selector in panel_open_selectors:
                    try:
                        if page.query_selector(selector):
                            panel_already_open = True
                            logger.info(f"Messaging panel is already open (found: {selector})")
                            break
                    except:
                        continue

                if not panel_already_open:
                    # Look for the floating messaging button at bottom right
                    # It's typically a bubble/header that shows "Messaging"
                    messaging_button_selectors = [
                        # The header bar of the messaging widget (clickable to expand)
                        ".msg-overlay-list-bubble__header",
                        ".msg-overlay-list-bubble__default-header",
                        # Floating messaging bubble header button
                        ".msg-overlay-bubble-header",
                        "button.msg-overlay-bubble-header__button",
                        # The messaging dock/tray at bottom
                        ".msg-overlay-list-bubble",
                        # Alternative: look for the messaging trigger
                        "[data-control-name='overlay.open_messaging_overlay']",
                        "button[aria-label='Open messaging overlay']",
                        ".msg-overlay-list-bubble-search__search-trigger",
                    ]

                    messaging_button = None
                    for selector in messaging_button_selectors:
                        try:
                            messaging_button = page.query_selector(selector)
                            if messaging_button:
                                logger.info(f"Found messaging button with selector: {selector}")
                                break
                        except:
                            continue

                    if messaging_button:
                        messaging_button.click()
                        page.wait_for_timeout(1500)
                        _human_delay_medium()
                    else:
                        # If no floating button found, the messaging widget might be minimized
                        # Try clicking on any minimized messaging element
                        logger.info("No floating button found, trying to find minimized messaging widget...")

                        minimized_selectors = [
                            ".msg-overlay-list-bubble--is-minimized",
                            ".msg-overlay__bubble-minimized",
                        ]

                        for selector in minimized_selectors:
                            try:
                                minimized = page.query_selector(selector)
                                if minimized:
                                    minimized.click()
                                    page.wait_for_timeout(1000)
                                    logger.info(f"Clicked minimized messaging widget: {selector}")
                                    break
                            except:
                                continue

                    # Wait for the messaging overlay panel to be open and showing conversations
                    # (only if we clicked to open it)
                    logger.info("Waiting for messaging panel to open...")
                    try:
                        page.wait_for_selector(".msg-overlay-list-bubble--is-open, .msg-overlay-list-bubble__conversations-container, .msg-conversations-container", timeout=10000)
                        logger.info("Messaging panel is now open")
                    except:
                        logger.warning("Messaging panel did not appear, trying to continue anyway...")

                for contact in contacts:
                    self.check_abort()

                    name = contact.get("name", "")
                    public_id = contact.get("public_id", "")

                    if not name:
                        continue

                    logger.info(f"Checking for reply from {name}...")

                    try:
                        # Search for the conversation with this person in the messaging overlay
                        # The search input is inside the messaging overlay panel
                        search_input_selectors = [
                            ".msg-overlay-list-bubble input[placeholder*='Search']",
                            ".msg-overlay-list-bubble input[type='search']",
                            ".msg-overlay-list-bubble input",
                            ".msg-overlay-container input[placeholder*='Search']",
                            ".msg-search-form input",
                            "input[placeholder*='Search messages']",
                            ".msg-overlay-list-bubble__search-container input",
                            # Alternative: the search trigger button that reveals the input
                            ".msg-overlay-list-bubble-search__search-typeahead-input",
                            ".msg-overlay-list-bubble input[aria-label*='Search']",
                        ]

                        search_input = None
                        for selector in search_input_selectors:
                            try:
                                search_input = page.query_selector(selector)
                                if search_input:
                                    logger.info(f"Found search input with selector: {selector}")
                                    break
                            except:
                                continue

                        if search_input:
                            # Click to focus, then clear and type
                            try:
                                search_input.click()
                                page.wait_for_timeout(200)
                            except:
                                pass
                            search_input.fill("")
                            page.wait_for_timeout(300)
                            search_input.fill(name)
                            page.wait_for_timeout(1500)  # Give more time for search results
                        else:
                            logger.warning(f"Could not find search input in messaging panel")
                            # Try to log what we can see for debugging
                            try:
                                panel_html = page.evaluate("() => document.querySelector('.msg-overlay-list-bubble')?.innerHTML?.substring(0, 500) || 'No panel found'")
                                logger.debug(f"Panel HTML preview: {panel_html[:200] if panel_html else 'None'}...")
                            except:
                                pass

                        # Look for conversation in the messaging overlay list
                        conversation_selectors = [
                            f".msg-overlay-list-bubble li:has-text('{name}')",
                            f".msg-conversation-listitem:has-text('{name}')",
                            f".msg-conversations-container__convo-item:has-text('{name}')",
                            f".msg-overlay-list-bubble__convo-card:has-text('{name}')",
                        ]

                        conversation = None
                        for selector in conversation_selectors:
                            try:
                                conversation = page.query_selector(selector)
                                if conversation:
                                    break
                            except:
                                continue

                        if not conversation:
                            logger.info(f"No conversation found with {name}")
                            page.wait_for_timeout(500)
                            continue

                        # Click to open the conversation
                        logger.info(f"Found conversation with {name}, clicking to open...")
                        conversation.click()
                        page.wait_for_timeout(2000)  # Give more time for conversation to load

                        # Wait for the conversation bubble to actually open
                        # The conversation opens in a separate bubble/window
                        conversation_opened = False
                        convo_bubble_selectors = [
                            ".msg-overlay-conversation-bubble",
                            ".msg-convo-wrapper",
                            ".msg-s-message-list",
                            ".msg-overlay-conversation-bubble--is-active",
                        ]

                        for selector in convo_bubble_selectors:
                            try:
                                convo_bubble = page.query_selector(selector)
                                if convo_bubble:
                                    conversation_opened = True
                                    logger.info(f"Conversation bubble opened (found: {selector})")
                                    break
                            except:
                                continue

                        if not conversation_opened:
                            logger.warning(f"Conversation bubble didn't open for {name}, trying alternative methods...")

                            # Try clicking on a more specific element within the conversation card
                            # The conversation might need a double-click or a specific child element click
                            try:
                                # Try finding and clicking on the name/title within the conversation card
                                name_element = conversation.query_selector("span, a, .msg-conversation-listitem__participant-names")
                                if name_element:
                                    name_element.click()
                                    page.wait_for_timeout(2000)
                                    logger.info(f"Clicked on name element within conversation card")
                                else:
                                    # Try double-clicking
                                    conversation.dblclick()
                                    page.wait_for_timeout(2000)
                                    logger.info(f"Double-clicked on conversation")
                            except Exception as click_error:
                                logger.warning(f"Alternative click failed: {click_error}")

                            # Check again if conversation opened
                            for selector in convo_bubble_selectors:
                                try:
                                    convo_bubble = page.query_selector(selector)
                                    if convo_bubble:
                                        conversation_opened = True
                                        logger.info(f"Conversation bubble now opened (found: {selector})")
                                        break
                                except:
                                    continue

                        if not conversation_opened:
                            logger.warning(f"Could not open conversation for {name}, skipping...")
                            page.wait_for_timeout(500)
                            continue

                        # Check if there's a reply - look for ANY inbound message in the conversation
                        # If they sent us ANY message, it means they replied (regardless of who sent last)
                        # Pass the contact name so we can check if messages are from them
                        reply_check_result = page.evaluate("""
                            (contactName) => {
                                // Look in the conversation bubble/overlay - try multiple selectors
                                const bubbleSelectors = [
                                    '.msg-overlay-conversation-bubble',
                                    '.msg-convo-wrapper',
                                    '.msg-s-message-list',
                                    '.msg-s-message-list-container',
                                    '[data-test-id="message-list"]'
                                ];

                                let bubble = null;
                                for (const sel of bubbleSelectors) {
                                    bubble = document.querySelector(sel);
                                    if (bubble) break;
                                }

                                if (!bubble) {
                                    return { found: false, error: 'No conversation bubble found' };
                                }

                                // Find all message events/groups - try multiple patterns
                                let messageItems = bubble.querySelectorAll('.msg-s-message-list__event');
                                if (messageItems.length === 0) {
                                    messageItems = bubble.querySelectorAll('.msg-s-message-group');
                                }
                                if (messageItems.length === 0) {
                                    messageItems = bubble.querySelectorAll('[class*="message-list__event"]');
                                }

                                if (messageItems.length === 0) {
                                    return { found: false, error: 'No message items found', bubbleHTML: bubble.innerHTML.substring(0, 500) };
                                }

                                // Get the first part of the contact's name for matching (e.g., "Arad" from "Arad Zilberstein")
                                const contactFirstName = contactName.split(' ')[0].toLowerCase();

                                // Count inbound (from them) and outbound (from us) messages
                                let inboundCount = 0;
                                let outboundCount = 0;
                                let inboundPreview = '';
                                let debugInfo = [];

                                for (const item of messageItems) {
                                    const classes = item.className.toLowerCase();
                                    const itemText = item.textContent || '';
                                    const itemHTML = item.innerHTML || '';

                                    // Default assumption: message is OUTBOUND (from us)
                                    // We only count as inbound if we have positive evidence it's from them
                                    // This prevents false positives where we sent a message and it looks like a reply
                                    let isInbound = false;
                                    let detectionMethod = 'default_outbound';

                                    // Method 1: Check for explicit CSS classes
                                    if (classes.includes('outbound')) {
                                        isInbound = false;
                                        detectionMethod = 'outbound_class';
                                    } else if (classes.includes('inbound')) {
                                        isInbound = true;
                                        detectionMethod = 'inbound_class';
                                    }

                                    // Method 2: Look for their profile image/avatar (indicates their message)
                                    if (!isInbound) {
                                        const avatarSelectors = [
                                            '.msg-s-message-group__profile-image',
                                            '.presence-entity__image',
                                            'img[class*="profile"]',
                                            '.msg-s-event-listitem__avatar img'
                                        ];
                                        for (const sel of avatarSelectors) {
                                            const avatar = item.querySelector(sel);
                                            if (avatar) {
                                                const avatarAlt = (avatar.alt || '').toLowerCase();
                                                // If avatar contains their name, this is THEIR message
                                                if (avatarAlt && avatarAlt.includes(contactFirstName)) {
                                                    isInbound = true;
                                                    detectionMethod = 'avatar_contains_name: ' + avatarAlt;
                                                    break;
                                                }
                                            }
                                        }
                                    }

                                    // Method 3: Check for sender name element showing their name
                                    if (!isInbound) {
                                        const senderSelectors = [
                                            '.msg-s-message-group__name',
                                            '.msg-s-event-listitem__name',
                                            '[class*="sender"]',
                                            '[class*="author"]'
                                        ];
                                        for (const sel of senderSelectors) {
                                            const senderEl = item.querySelector(sel);
                                            if (senderEl) {
                                                const senderText = senderEl.textContent.toLowerCase().trim();
                                                // If sender element shows their name, it's their message
                                                if (senderText && senderText.includes(contactFirstName)) {
                                                    isInbound = true;
                                                    detectionMethod = 'sender_name_match: ' + senderText;
                                                    break;
                                                }
                                            }
                                        }
                                    }

                                    // Method 4: Check the message item structure for participant indicators
                                    if (!isInbound) {
                                        // LinkedIn may show participant name in message group header
                                        const participantName = item.querySelector('.msg-s-message-group__participant-name');
                                        if (participantName) {
                                            const nameText = participantName.textContent.toLowerCase().trim();
                                            if (nameText.includes(contactFirstName)) {
                                                isInbound = true;
                                                detectionMethod = 'participant_name: ' + nameText;
                                            }
                                        }
                                    }

                                    const isOutbound = !isInbound;

                                    debugInfo.push({
                                        classes: classes.substring(0, 100),
                                        isOutbound: isOutbound,
                                        isInbound: isInbound,
                                        method: detectionMethod,
                                        textPreview: itemText.substring(0, 50)
                                    });

                                    if (isOutbound) {
                                        outboundCount++;
                                    } else {
                                        // This is an inbound message (from them) - they replied!
                                        inboundCount++;
                                        if (!inboundPreview) {
                                            inboundPreview = item.outerHTML.substring(0, 200);
                                        }
                                    }
                                }

                                // If there's ANY inbound message, they replied
                                const hasReply = inboundCount > 0;

                                return {
                                    found: true,
                                    totalMessages: messageItems.length,
                                    inboundCount: inboundCount,
                                    outboundCount: outboundCount,
                                    hasReply: hasReply,
                                    inboundPreview: inboundPreview,
                                    contactFirstName: contactFirstName,
                                    debug: debugInfo
                                };
                            }
                        """, name)

                        # Log the detailed result
                        logger.info(f"Reply check result for {name}: {reply_check_result}")

                        has_reply = reply_check_result.get('hasReply', False) if isinstance(reply_check_result, dict) else False

                        if has_reply:
                            logger.info(f"Found reply from {name}!")
                            replied_contacts.append(contact)
                        else:
                            logger.info(f"No reply yet from {name}")

                        # Close the conversation bubble to go back to the list
                        page.evaluate("""
                            () => {
                                const closeButtons = document.querySelectorAll(
                                    '.msg-overlay-conversation-bubble button[aria-label*="Close"], ' +
                                    '.msg-overlay-bubble-header button[aria-label*="Close"]'
                                );
                                for (const btn of closeButtons) {
                                    try { btn.click(); } catch(e) {}
                                }
                            }
                        """)
                        page.wait_for_timeout(500)

                    except WorkflowAbortedException:
                        raise
                    except Exception as e:
                        logger.warning(f"Error checking reply from {name}: {e}")
                        continue

                return replied_contacts

            except WorkflowAbortedException:
                raise
            except Exception as e:
                logger.error(f"Error checking for replies: {e}")
                return replied_contacts

            finally:
                # ALWAYS close the browser
                if context:
                    try:
                        logger.info("Closing browser after reply check...")
                        context.close()
                        logger.info("Browser closed after reply check")
                    except Exception as close_error:
                        logger.warning(f"Error closing browser: {close_error}")


# Global client instance
def get_linkedin_client() -> LinkedInClient:
    """Get the global LinkedIn client instance."""
    return LinkedInClient.get_instance()
