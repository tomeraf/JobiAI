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

    async def search_company_all_degrees(self, company: str, limit: int = 15, message_generator=None) -> dict:
        """
        Search for people at a company - first 1st degree, then 2nd degree, then 3rd+ if needed.
        All in a single browser session for efficiency.

        Args:
            company: Company name to search for
            limit: Maximum results per degree level
            message_generator: Optional function(name, company) -> str to generate message text
                              for 1st degree connections

        Returns:
            dict with 'first_degree', 'second_degree', 'third_plus', and 'messages_sent' lists
        """
        if not self._logged_in:
            logger.error("Not logged in")
            return {"first_degree": [], "second_degree": [], "third_plus": []}

        return await _run_playwright_async(self._search_company_all_degrees_sync, company, limit, message_generator)

    def _search_company_all_degrees_sync(self, company: str, limit: int, message_generator=None) -> dict:
        """
        Synchronous combined search for 1st, 2nd, and 3rd+ degree connections at a company.
        Keeps browser open between searches.
        For 2nd/3rd+ degree: clicks Connect button directly on search results page.
        For 1st degree: sends messages using the provided message_generator function.
        """
        if not HAS_PLAYWRIGHT:
            logger.error("Playwright not installed!")
            return {"first_degree": [], "second_degree": [], "third_plus": [], "connection_requests_sent": []}

        result = {"first_degree": [], "second_degree": [], "third_plus": [], "connection_requests_sent": []}
        logger.info(f"Starting combined search for connections at: {company}")

        with sync_playwright() as p:
            try:
                logger.info(f"Running in {'FAST' if FAST_MODE else 'SAFE'} mode (delays: {DELAY_MS}ms)")

                context = p.chromium.launch_persistent_context(
                    str(BROWSER_DATA_PATH),
                    headless=False,
                    viewport={"width": 1280, "height": 720},
                    args=["--window-size=1300,750", "--window-position=100,100"],  # Override maximized state
                )
                page = context.pages[0] if context.pages else context.new_page()

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
                    context.close()
                    return result

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
                    context.close()
                    return result

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
                    messaged_people = self._send_messages_on_search_page(page, company, message_generator=message_generator, num_pages=1)
                    result["messages_sent"] = messaged_people
                    messages_sent_count = len(messaged_people)
                    logger.info(f"Sent {messages_sent_count} messages from search page")
                elif first_degree:
                    logger.info(f"Found {len(first_degree)} 1st degree connections (skipping messages - no generator provided)")

                # Step 6: If no 1st degree found OR all 1st degree were skipped (existing history), switch to 2nd degree
                # This ensures we continue the flow instead of failing when all contacts have been previously messaged
                should_try_2nd_degree = not first_degree or (first_degree and message_generator and messages_sent_count == 0)

                if should_try_2nd_degree:
                    # Check for abort before 2nd degree
                    self.check_abort()

                    if first_degree:
                        logger.info(f"All {len(first_degree)} 1st degree connections were skipped (existing history), trying 2nd degree...")
                    else:
                        logger.info("No 1st degree found, switching to 2nd degree filter...")
                    self._apply_connection_filter(page, "2nd")

                    # Send connection requests directly on search page (2 pages)
                    connected_people = self._send_connection_requests_on_search_page(page, company, num_pages=2)
                    result["second_degree"] = connected_people
                    result["connection_requests_sent"] = connected_people
                    logger.info(f"Sent {len(connected_people)} connection requests to 2nd degree people")

                    # Step 6: If no 2nd degree connected, try 3rd+ degree
                    if not connected_people:
                        # Check for abort before 3rd+ degree
                        self.check_abort()

                        logger.info("No 2nd degree found with Connect button, switching to 3rd+ degree filter...")
                        self._apply_connection_filter(page, "3rd+")

                        # Send connection requests directly on search page (2 pages)
                        connected_people_3rd = self._send_connection_requests_on_search_page(page, company, num_pages=2)
                        result["third_plus"] = connected_people_3rd
                        result["connection_requests_sent"] = connected_people_3rd
                        logger.info(f"Sent {len(connected_people_3rd)} connection requests to 3rd+ degree people")

                context.close()
                return result

            except WorkflowAbortedException:
                logger.info("Workflow aborted by user - closing browser")
                try:
                    context.close()
                except:
                    pass
                raise  # Re-raise to propagate abort

            except Exception as e:
                logger.error(f"Combined search failed: {e}", exc_info=True)
                return result

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

                # Step 1: Go to LinkedIn feed page
                logger.info("Step 1: Going to LinkedIn feed page...")
                page.goto("https://www.linkedin.com/feed/", timeout=60000)
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

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

    def _send_connection_requests_on_search_page(self, page, company: str, num_pages: int = 2) -> list[dict]:
        """
        Send connection requests directly from search results page.
        Only clicks "Connect" buttons - skips people with Message/Follow buttons.
        Processes multiple pages of results.

        Args:
            page: Playwright page object
            company: Company name to match
            num_pages: Number of pages to process (default 2)

        Returns list of people who were successfully sent connection requests.
        """
        connected_people = []
        company_lower = company.lower()

        for page_num in range(1, num_pages + 1):
            # Check for abort at start of each page
            self.check_abort()

            logger.info(f"Processing page {page_num} of {num_pages}")

            # Wait for results to load (with abort check)
            self._wait_with_abort_check(page, DELAY_MS)

            # Process current page
            page_results = self._process_search_results_page(page, company_lower, connected_people)
            connected_people.extend(page_results)
            logger.info(f"Page {page_num}: sent {len(page_results)} connection requests (total: {len(connected_people)})")

            # Go to next page if not on last page
            if page_num < num_pages:
                if not self._go_to_next_search_page(page):
                    logger.info("No more pages available")
                    break

        logger.info(f"Sent {len(connected_people)} total connection requests from {page_num} page(s)")
        return connected_people

    def _go_to_next_search_page(self, page) -> bool:
        """Navigate to the next search results page. Returns True if successful."""
        try:
            # Look for "Next" button
            next_btn = page.query_selector("button[aria-label='Next']")
            if not next_btn:
                next_btn = page.query_selector("button:has-text('Next')")
            if not next_btn:
                # Try pagination link
                next_btn = page.query_selector("a[aria-label='Next']")

            if next_btn and next_btn.is_enabled():
                logger.info("Clicking Next button to go to next page")
                next_btn.click()
                page.wait_for_timeout(DELAY_MS * 2)  # Wait for page to load
                return True
            else:
                logger.info("Next button not found or disabled")
                return False
        except WorkflowAbortedException:
            raise  # Re-raise abort exception immediately
        except Exception as e:
            logger.error(f"Error navigating to next page: {e}")
            return False

    def _process_search_results_page(self, page, company_lower: str, already_connected: list) -> list[dict]:
        """Process all results on the current search page."""
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

                # Look for Connect button in this result item with retry
                connect_btn_selectors = [
                    "button:has-text('Connect')",
                    "button[aria-label*='connect']",
                ]
                connect_btn = self._retry_find_in_element(page, result, connect_btn_selectors, f"find Connect button for {name}")

                if not connect_btn:
                    # No Connect button - person has Message, Follow, or other button
                    logger.info(f"Skipping {name} - no Connect button (has Message/Follow/other)")
                    continue

                # Found Connect button - click it
                logger.info(f"Clicking Connect for: {name}")
                connect_btn.click()
                page.wait_for_timeout(DELAY_MS)

                # Handle the connection modal with retry logic
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
                    # Modal might have "Add a note" option - click Send without note
                    # Or close the modal if we can't find send
                    close_btn = page.query_selector("button[aria-label='Dismiss']")
                    if close_btn:
                        close_btn.click()
                        page.wait_for_timeout(DELAY_MS // 2)
                    logger.warning(f"Could not find Send button for {name}: {send_error}")

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

    def _send_messages_on_search_page(self, page, company: str, message_generator=None, num_pages: int = 1) -> list[dict]:
        """
        Send messages to 1st degree connections directly from search results page.
        Clicks Message button on each person's card, types message in modal, and sends.

        Args:
            page: Playwright page object
            company: Company name to match
            message_generator: Optional function(name, company) -> str to generate message text.
                              If None, uses a default message.
            num_pages: Number of pages to process (default 1)

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
            page_results = self._process_message_results_page(page, company_lower, already_messaged=messaged_people, message_generator=message_generator)
            messaged_people.extend(page_results)
            logger.info(f"Page {page_num}: sent {len(page_results)} messages (total: {len(messaged_people)})")

            # Go to next page if not on last page
            if page_num < num_pages:
                if not self._go_to_next_search_page(page):
                    logger.info("No more pages available")
                    break

        logger.info(f"Sent {len(messaged_people)} total messages from {page_num} page(s)")
        return messaged_people

    def _process_message_results_page(self, page, company_lower: str, already_messaged: list, message_generator=None) -> list[dict]:
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

                # Check if there's existing message history in the chat
                # If we've messaged this person before or they messaged us, skip them
                has_existing_history = False
                try:
                    # Use JavaScript to check for message history in the chat modal dialog
                    # The chat popup is a DIV with role="dialog" (NOT an HTML <dialog> element!)
                    # It also has class msg-overlay-conversation-bubble
                    # Each message is a listitem with a paragraph. We count listitems with paragraphs to detect history.
                    message_count = page.evaluate("""
                        () => {
                            // Find the messaging dialog - it's a DIV with role="dialog", NOT <dialog> HTML element
                            // The accessibility tree shows "dialog" but actual DOM is div[role="dialog"]
                            const dialog = document.querySelector('[role="dialog"]') || document.querySelector('.msg-overlay-conversation-bubble');
                            if (!dialog) {
                                console.log('No dialog found');
                                return -1;  // Return -1 to indicate dialog not found
                            }

                            // Find the message list within the dialog (it's a <ul> element)
                            const messageList = dialog.querySelector('ul');
                            if (!messageList) {
                                console.log('No message list found in dialog');
                                return -2;  // Return -2 to indicate list not found
                            }

                            // Count list items that contain actual message content (paragraphs with text)
                            // Empty listitems are just spacers
                            const listItems = messageList.querySelectorAll('li');
                            let messageCount = 0;
                            listItems.forEach(li => {
                                // Check if this list item has a paragraph with actual text content
                                const paragraph = li.querySelector('p');
                                if (paragraph && paragraph.textContent.trim().length > 5) {
                                    messageCount++;
                                }
                            });
                            return messageCount;
                        }
                    """)

                    logger.info(f"Message history check for {name}: found {message_count} messages")

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
                        message_text = message_generator(name, company_lower)
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
                    except WorkflowAbortedException:
                        raise  # Re-raise abort exception immediately
                    except Exception as send_error:
                        logger.warning(f"Could not find Send button for {name}: {send_error}")
                        # Close the modal
                        close_btn = page.query_selector("button[aria-label='Dismiss']")
                        if close_btn:
                            close_btn.click()
                            page.wait_for_timeout(300)

                except WorkflowAbortedException:
                    raise  # Re-raise abort exception immediately
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

            except WorkflowAbortedException:
                raise  # Re-raise abort exception immediately

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
                logger.info("Browser launched, navigating to connections page...")

                # Go to connections page
                page.goto("https://www.linkedin.com/mynetwork/invite-connect/connections/", timeout=60000)
                logger.info("Page loaded, waiting for DOM...")
                # Use domcontentloaded instead of networkidle (faster, more reliable)
                page.wait_for_load_state("domcontentloaded", timeout=30000)

                # Wait a bit for dynamic content to load
                logger.info("DOM loaded, waiting for dynamic content...")
                page.wait_for_timeout(3000)

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

                # Step 1: Go to LinkedIn feed page
                logger.info("Step 1: Going to LinkedIn feed page...")
                page.goto("https://www.linkedin.com/feed/", timeout=60000)
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

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

                # Go to the person's profile
                page.goto(f"https://www.linkedin.com/in/{public_id}/")
                page.wait_for_load_state("networkidle")

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

                # Go to the person's profile
                page.goto(f"https://www.linkedin.com/in/{public_id}/")
                page.wait_for_load_state("networkidle")

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


# Global client instance
def get_linkedin_client() -> LinkedInClient:
    """Get the global LinkedIn client instance."""
    return LinkedInClient.get_instance()
