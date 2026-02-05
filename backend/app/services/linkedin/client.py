"""
LinkedIn Client using Playwright persistent context.

Uses a persistent browser context to maintain login state across sessions.
This is more reliable than cookie extraction as it maintains the full
browser environment including localStorage, sessionStorage, and cookies.
"""
import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor

from app.utils.logger import get_logger
from .selectors import LinkedInSelectors, conversation_selectors
from .vip_filter import is_vip
from .extractors import (
    extract_person_from_search_result,
    extract_people_from_search_results,
    extract_connection_from_card,
)
from .browser_utils import (
    BROWSER_DATA_PATH, DELAY_MS, FAST_MODE,
    ensure_browser_data_dir, get_browser_args,
    RetryHelper, ChatModalHelper, bring_browser_to_front,
)
from .js_scripts import (
    get_message_history_script,
    get_reply_check_script,
    get_close_current_chat_script,
)

logger = get_logger(__name__)

# Create a dedicated thread pool for Playwright operations
_playwright_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")

# Try to import playwright
try:
    from playwright.sync_api import sync_playwright, Page
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
    """Run a synchronous Playwright function with correct Windows event loop."""
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return func(*args, **kwargs)


async def _run_playwright_async(func, *args, **kwargs):
    """Run a synchronous Playwright function asynchronously."""
    loop = asyncio.get_event_loop()
    def wrapper():
        return _run_sync_playwright(func, *args, **kwargs)
    return await loop.run_in_executor(_playwright_executor, wrapper)


class WorkflowAbortedException(Exception):
    """Raised when workflow is aborted by user."""
    pass


class MissingHebrewNamesException(Exception):
    """Raised when Hebrew name translations are needed but not available."""
    def __init__(self, missing_names: list[str], first_degree_found: list[dict] = None):
        self.missing_names = missing_names
        self.first_degree_found = first_degree_found or []
        super().__init__(f"Missing Hebrew translations for: {', '.join(missing_names)}")


def _apply_stealth(page):
    """Apply stealth patches to a page to avoid bot detection."""
    if HAS_STEALTH:
        try:
            stealth_sync(page)
            logger.debug("Stealth patches applied to page")
        except Exception as e:
            logger.warning(f"Failed to apply stealth patches: {e}")


class LinkedInClient:
    """
    LinkedIn client using Playwright with persistent browser context.
    Singleton pattern - one instance across the application.

    The browser stays open between operations for faster subsequent calls.
    """

    _instance: "LinkedInClient | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._logged_in = False
            cls._instance._email = None
            cls._instance._name = None
            cls._instance._playwright = None
            cls._instance._browser = None
            cls._instance._context = None
            cls._instance._page = None
            cls._instance._abort_requested = False
            cls._instance._current_job_id = None
            cls._instance._queued_jobs = []
        return cls._instance

    def __init__(self):
        pass

    def _get_or_create_browser(self):
        """
        Get existing browser context or create a new one.
        Keeps both playwright instance and browser open between operations for speed.
        """
        # If we have an existing context, try to use it
        if self._context is not None and self._playwright is not None:
            try:
                # Check if context is still valid by getting pages
                pages = self._context.pages
                if pages:
                    self._page = pages[0]
                    logger.info("Reusing existing browser context")
                    return self._context, self._page
            except Exception as e:
                logger.info(f"Existing context invalid: {e}, creating new one")
                self._cleanup_browser()

        # Create new playwright instance if needed
        if self._playwright is None:
            logger.info("Starting Playwright...")
            self._playwright = sync_playwright().start()

        # Create new context
        logger.info("Creating new browser context...")
        ensure_browser_data_dir()
        self._context = self._playwright.chromium.launch_persistent_context(
            str(BROWSER_DATA_PATH),
            **get_browser_args()
        )
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        self._page.set_default_timeout(10000)
        _apply_stealth(self._page)
        return self._context, self._page

    def _cleanup_browser(self):
        """Clean up browser context but keep playwright instance."""
        if self._context:
            try:
                self._context.close()
            except:
                pass
        self._context = None
        self._page = None

    def close_browser(self):
        """Explicitly close the browser and playwright (call when shutting down)."""
        if self._context:
            try:
                logger.info("Closing browser context...")
                if self._page:
                    ChatModalHelper.close_all_overlays(self._page)
                self._context.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
            finally:
                self._context = None
                self._page = None

        if self._playwright:
            try:
                logger.info("Stopping Playwright...")
                self._playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")
            finally:
                self._playwright = None

    @classmethod
    def get_instance(cls) -> "LinkedInClient":
        return cls()

    # --- Abort and Queue Management ---

    def request_abort(self, job_id: int | None = None):
        self._abort_requested = True
        logger.info(f"Abort requested for job {job_id if job_id else 'current'}")

    def clear_abort(self):
        self._abort_requested = False

    def is_abort_requested(self) -> bool:
        return self._abort_requested

    def check_abort(self):
        if self._abort_requested:
            raise WorkflowAbortedException("Workflow aborted by user")

    def set_current_job(self, job_id: int | None):
        self._current_job_id = job_id

    def get_current_job(self) -> int | None:
        return self._current_job_id

    def add_to_queue(self, job_id: int):
        if job_id not in self._queued_jobs:
            self._queued_jobs.append(job_id)
            logger.info(f"Job {job_id} added to queue. Queue: {self._queued_jobs}")

    def remove_from_queue(self, job_id: int):
        if job_id in self._queued_jobs:
            self._queued_jobs.remove(job_id)
            logger.info(f"Job {job_id} removed from queue. Queue: {self._queued_jobs}")

    def get_queued_jobs(self) -> list[int]:
        return list(self._queued_jobs)

    def is_job_queued(self, job_id: int) -> bool:
        return job_id in self._queued_jobs

    def _wait_with_abort_check(self, page, ms: int):
        """Wait for specified ms, checking for abort every 500ms."""
        remaining = ms
        while remaining > 0:
            self.check_abort()
            wait_time = min(remaining, 500)
            page.wait_for_timeout(wait_time)
            remaining -= wait_time

    # --- Authentication ---

    async def login_with_browser(self) -> bool:
        """Open a browser window for manual LinkedIn login."""
        if not HAS_PLAYWRIGHT:
            logger.error("playwright not installed")
            return False

        try:
            logger.info("Opening browser for LinkedIn login...")
            ensure_browser_data_dir()
            result = await _run_playwright_async(self._browser_login_flow)

            if result:
                self._logged_in = True
                self._name = result.get("name")
                self._email = result.get("email")
                logger.info(f"LinkedIn login successful! Welcome {self._name}")
                return True
            return False

        except Exception as e:
            logger.error(f"Browser login failed: {e}")
            self._logged_in = False
            return False

    def _browser_login_flow(self) -> dict | None:
        """Synchronous browser login flow."""
        context = None
        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    str(BROWSER_DATA_PATH),
                    **get_browser_args(maximized=True)
                )

                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(10000)
                _apply_stealth(page)
                page.bring_to_front()
                bring_browser_to_front()

                # Logout first for fresh login
                logger.info("Clearing any existing LinkedIn session...")
                try:
                    page.goto("https://www.linkedin.com/m/logout/", wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(1000)
                except Exception:
                    return None

                # Go to login page
                try:
                    page.goto("https://www.linkedin.com/login")
                except Exception:
                    return None

                logger.info("Browser opened - please login to LinkedIn")

                # Poll for login success
                import time
                start_time = time.time()
                timeout_seconds = 300

                while True:
                    if time.time() - start_time > timeout_seconds:
                        logger.info("Login timed out")
                        context.close()
                        return None

                    try:
                        if page.is_closed():
                            return None
                        current_url = page.url
                        if "/feed" in current_url or "/mynetwork" in current_url or "/in/" in current_url:
                            logger.info("Login detected!")
                            break
                    except Exception:
                        return None

                    try:
                        page.wait_for_timeout(500)
                    except:
                        return None

                profile = self._get_profile_from_page(page)
                context.close()
                return profile

        except Exception as e:
            error_str = str(e).lower()
            if "target page" in error_str or "closed" in error_str:
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
            name = None
            nav_profile = page.query_selector(LinkedInSelectors.NAV_PROFILE_PHOTO)
            if nav_profile:
                name = nav_profile.get_attribute("alt")
                if name:
                    name = name.replace("Photo of ", "").strip()

            if not name:
                try:
                    page.goto("https://www.linkedin.com/in/me/", timeout=15000)
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    name_element = page.query_selector("h1")
                    if name_element:
                        name = name_element.inner_text().strip()
                except Exception:
                    pass

            return {"name": name, "email": None}
        except Exception as e:
            logger.error(f"Error getting profile: {e}")
            return {"name": None, "email": None}

    async def check_session(self) -> bool:
        """Check if we have a valid LinkedIn session."""
        if self._logged_in:
            return True

        if not BROWSER_DATA_PATH.exists():
            return False

        try:
            result = await _run_playwright_async(self._verify_session)
            if result:
                self._logged_in = True
                self._name = result.get("name")
                logger.info(f"Session valid, logged in as: {self._name}")
                return True
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
                context = p.chromium.launch_persistent_context(
                    str(BROWSER_DATA_PATH),
                    headless=True,
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(10000)
                _apply_stealth(page)

                page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)

                if "/login" in page.url or "/checkpoint" in page.url:
                    context.close()
                    return None

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

        if BROWSER_DATA_PATH.exists():
            try:
                shutil.rmtree(BROWSER_DATA_PATH)
                logger.info("LinkedIn browser context cleared")
            except Exception as e:
                logger.error(f"Error clearing browser context: {e}")

    async def get_profile_info(self) -> dict:
        return {"name": self._name, "email": self._email}

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in

    # --- LinkedIn Search Operations ---

    async def search_company_all_degrees(self, company: str, limit: int = 15, message_generator=None, first_degree_only: bool = False) -> dict:
        """Search for people at a company - 1st degree first, then 2nd/3rd if needed."""
        if not self._logged_in:
            logger.error("Not logged in")
            return {"first_degree": [], "second_degree": [], "third_plus": []}

        return await _run_playwright_async(
            self._search_company_all_degrees_sync, company, limit, message_generator, first_degree_only
        )

    def _search_company_all_degrees_sync(self, company: str, limit: int, message_generator=None, first_degree_only: bool = False) -> dict:
        """Synchronous combined search for all degree connections."""
        if not HAS_PLAYWRIGHT:
            return {"first_degree": [], "second_degree": [], "third_plus": [], "connection_requests_sent": []}

        result = {"first_degree": [], "second_degree": [], "third_plus": [], "connection_requests_sent": []}
        logger.info(f"Starting combined search for connections at: {company}")

        try:
            logger.info(f"Running in {'FAST' if FAST_MODE else 'SAFE'} mode (delays: {DELAY_MS}ms)")
            import time
            launch_start = time.time()
            context, page = self._get_or_create_browser()
            launch_time = time.time() - launch_start
            logger.info(f"Browser ready in {launch_time:.1f}s")

            self.check_abort()

            # Step 1: Go to LinkedIn feed
            logger.info("Step 1: Going to LinkedIn feed page...")
            page.goto("https://www.linkedin.com/feed/", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            self._wait_with_abort_check(page, DELAY_MS)

            # Step 2: Search for company
            logger.info(f"Step 2: Searching for '{company}'...")
            search_input = RetryHelper.retry_find(page, LinkedInSelectors.SEARCH_INPUT, "find search input")
            search_input.click()
            page.wait_for_timeout(DELAY_MS // 2)
            search_input.fill(company)
            page.wait_for_timeout(DELAY_MS // 2)
            page.keyboard.press("Enter")

            page.wait_for_load_state("domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Step 3: Click People tab
            logger.info("Step 3: Clicking on People tab...")
            self._click_people_tab(page)

            self.check_abort()

            # Step 4: Filter by 1st degree
            logger.info("Step 4: Filtering by 1st degree connections...")
            self._apply_connection_filter(page, "1st")
            first_degree = extract_people_from_search_results(page, company)
            result["first_degree"] = first_degree
            logger.info(f"Found {len(first_degree)} 1st degree connections")

            self.check_abort()

            # Step 5: Send messages to 1st degree if found
            messages_sent_count = 0
            if first_degree and message_generator:
                logger.info(f"Sending messages to 1st degree connections...")
                messaged_people = self._send_messages_on_search_page(
                    page, company, message_generator, num_pages=1, first_degree_only=first_degree_only
                )
                result["messages_sent"] = messaged_people
                messages_sent_count = len(messaged_people)

            # Step 6: Fall back to 2nd/3rd degree if needed
            should_try_2nd = not first_degree or (first_degree and message_generator and messages_sent_count == 0)

            if first_degree_only:
                logger.info(f"First degree only mode: Sent {messages_sent_count} messages")
            elif should_try_2nd:
                self.check_abort()
                logger.info("Trying 2nd degree connections...")
                self._apply_connection_filter(page, "2nd")

                connected_people = self._send_connection_requests_on_search_page(page, company, max_requests=5)
                result["second_degree"] = connected_people
                result["connection_requests_sent"] = connected_people

                # Try 3rd+ if we haven't reached 5
                if len(connected_people) < 5:
                    self.check_abort()
                    remaining = 5 - len(connected_people)
                    logger.info(f"Trying 3rd+ degree for {remaining} more...")
                    self._apply_connection_filter(page, "3rd+")
                    connected_3rd = self._send_connection_requests_on_search_page(page, company, max_requests=remaining)
                    result["third_plus"] = connected_3rd
                    result["connection_requests_sent"] = connected_people + connected_3rd

            logger.info("Workflow complete")
            return result

        except (WorkflowAbortedException, MissingHebrewNamesException):
            raise
        except Exception as e:
            logger.error(f"Combined search failed: {e}", exc_info=True)
            return result
        finally:
            # Don't close browser - keep it open for next operation
            # Just close any open chat overlays
            try:
                if self._page:
                    ChatModalHelper.close_all_overlays(self._page)
            except Exception as e:
                logger.warning(f"Error closing overlays: {e}")

    def _click_people_tab(self, page) -> bool:
        """Click the People tab in search results."""
        if "/search/results/people" in page.url:
            return True

        try:
            RetryHelper.retry_click(page, LinkedInSelectors.PEOPLE_TAB, "click People tab")
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            return True
        except Exception:
            # Try direct URL navigation
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(page.url)
            params = parse_qs(parsed.query)
            keywords = params.get('keywords', [''])[0]

            if keywords:
                page.goto(f"https://www.linkedin.com/search/results/people/?keywords={keywords}")
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                return True
            raise

    def _apply_connection_filter(self, page, degree: str):
        """Apply connection degree filter."""
        # Clear other degree filters first
        other_degrees = ['1st', '2nd', '3rd+']
        if degree in other_degrees:
            other_degrees.remove(degree)

        for other in other_degrees:
            try:
                # Try new LinkedIn UI (2026) - radio buttons
                active_btn = page.query_selector(f"[role='radio']:has-text('{other}')")
                if active_btn:
                    # Check if it has checked state (via aria-checked or inner checkbox)
                    is_checked = active_btn.get_attribute("aria-checked") == "true"
                    if not is_checked:
                        checkbox = active_btn.query_selector("input[type='checkbox']:checked")
                        is_checked = checkbox is not None
                    if is_checked:
                        active_btn.click()
                        page.wait_for_timeout(500)
                        continue
                # Fallback to old selectors
                active_btn = page.query_selector(f"button:has-text('{other}')[aria-pressed='true']")
                if not active_btn:
                    active_btn = page.query_selector(f"button.artdeco-pill--selected:has-text('{other}')")
                if active_btn:
                    active_btn.click()
                    page.wait_for_timeout(500)
            except Exception:
                pass

        try:
            RetryHelper.retry_click(page, LinkedInSelectors.degree_filter(degree), f"click {degree} degree filter")
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
        except Exception:
            # Try dropdown approach
            try:
                RetryHelper.retry_click(page, LinkedInSelectors.CONNECTIONS_DROPDOWN, "click Connections dropdown")
                page.wait_for_timeout(1000)
                RetryHelper.retry_click(page, [f"label:has-text('{degree}')"], f"click {degree} option")
                page.wait_for_timeout(500)
                try:
                    RetryHelper.retry_click(page, LinkedInSelectors.SHOW_RESULTS, "click Show button")
                except Exception:
                    pass
                page.wait_for_timeout(2000)
            except Exception as e:
                raise Exception(f"Failed to apply {degree} filter: {e}")

    def _go_to_next_search_page(self, page) -> bool:
        """Navigate to the next search results page."""
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(500)

            next_btn = None
            for selector in LinkedInSelectors.NEXT_PAGE:
                next_btn = page.query_selector(selector)
                if next_btn:
                    break

            if next_btn and next_btn.is_enabled():
                next_btn.click()
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                page.wait_for_timeout(DELAY_MS * 2)
                return True
            return False
        except WorkflowAbortedException:
            raise
        except Exception as e:
            logger.error(f"Error navigating to next page: {e}")
            return False

    # --- Messaging Operations ---

    def _send_messages_on_search_page(self, page, company: str, message_generator=None, num_pages: int = 1, first_degree_only: bool = False) -> list[dict]:
        """Send messages to 1st degree connections from search results."""
        messaged_people = []
        company_lower = company.lower()

        for page_num in range(1, num_pages + 1):
            self.check_abort()
            logger.info(f"Processing page {page_num} for messaging")
            self._wait_with_abort_check(page, DELAY_MS)

            page_results = self._process_message_results_page(
                page, company_lower, messaged_people, message_generator, first_degree_only
            )
            messaged_people.extend(page_results)

            if first_degree_only and messaged_people:
                break

            if page_num < num_pages and not self._go_to_next_search_page(page):
                break

        return messaged_people

    def _process_message_results_page(self, page, company_lower: str, already_messaged: list, message_generator=None, first_degree_only: bool = False) -> list[dict]:
        """Process search results page to send messages."""
        page_messaged = []

        results = []
        for selector in LinkedInSelectors.SEARCH_RESULTS:
            results = page.query_selector_all(selector)
            if results:
                break

        if not results:
            return []

        already_messaged_urls = {p.get("linkedin_url") for p in already_messaged}

        for result in results:
            self.check_abort()

            try:
                person = extract_person_from_search_result(result, company_lower)
                if not person:
                    continue

                if is_vip(person.get("headline", "")):
                    logger.info(f"Skipping {person['name']} - VIP")
                    continue

                if person["linkedin_url"] in already_messaged_urls:
                    continue

                # Find Message button
                message_btn = RetryHelper.retry_find_in_element(
                    page, result, LinkedInSelectors.MESSAGE_BUTTON, f"find Message button for {person['name']}"
                )
                if not message_btn:
                    logger.info(f"Skipping {person['name']} - no Message button found")
                    continue

                # Close any existing chat before opening a new one
                if ChatModalHelper.is_modal_open(page):
                    logger.info(f"Closing existing chat before messaging {person['name']}")
                    ChatModalHelper.close_current_chat(page)
                    page.wait_for_timeout(500)

                # Log what element we found for debugging
                btn_tag = message_btn.evaluate("el => el.tagName")
                btn_href = message_btn.evaluate("el => el.href || 'none'")
                logger.info(f"Clicking Message for: {person['name']} (tag={btn_tag}, href={btn_href[:50] if btn_href != 'none' else 'none'})")

                url_before = page.url
                message_btn.click()
                page.wait_for_timeout(1500)  # Wait 1.5 seconds for modal to appear

                # Check if we navigated away (link click) vs modal opened
                url_after = page.url
                if url_after != url_before:
                    logger.info(f"Message click navigated to: {url_after[:80]}")
                    # If we navigated to messaging page, the conversation should be there
                    # Try to find the textbox on the messaging page
                    page.wait_for_timeout(1000)

                # Retry checking for modal a few times
                modal_found = False
                for attempt in range(3):
                    if ChatModalHelper.is_modal_open(page):
                        modal_found = True
                        break
                    page.wait_for_timeout(500)

                if not modal_found:
                    logger.info(f"Chat modal did not open for {person['name']}, skipping")
                    # If we navigated, go back
                    if url_after != url_before:
                        page.go_back()
                        page.wait_for_timeout(1000)
                    continue

                # Check for existing message history
                page.wait_for_timeout(500)
                history_result = page.evaluate(get_message_history_script())
                message_count = history_result.get('count', 0)

                if message_count > 0:
                    logger.info(f"Existing conversation with {person['name']} - skipping")
                    closed = ChatModalHelper.close_current_chat(page)
                    logger.info(f"Closed chat modal for {person['name']}: {closed}")
                    page.wait_for_timeout(300)  # Extra wait after closing
                    continue

                # Find message input and send
                try:
                    message_input = RetryHelper.retry_find(page, LinkedInSelectors.MESSAGE_INPUT, "find message input")

                    first_name = person['name'].split()[0]
                    if message_generator:
                        try:
                            message_text = message_generator(person['name'], company_lower)
                        except MissingHebrewNamesException:
                            page.evaluate(get_close_current_chat_script())
                            page.wait_for_timeout(300)
                            page.keyboard.press("Escape")
                            raise
                    else:
                        message_text = f"Hi {first_name}, I noticed you work at {company_lower}. I'd love to connect!"

                    message_input.click()
                    page.wait_for_timeout(300)
                    message_input.fill(message_text)
                    page.wait_for_timeout(500)

                    RetryHelper.retry_click(page, LinkedInSelectors.SEND_MESSAGE, f"click Send for {person['name']}")
                    logger.info(f"Message sent to: {person['name']}")

                    person["is_connection"] = True
                    person["message_sent"] = True
                    page_messaged.append(person)

                    page.wait_for_timeout(500)
                    ChatModalHelper.close_current_chat(page)

                    # Stop after first successful message
                    return page_messaged

                except (WorkflowAbortedException, MissingHebrewNamesException):
                    raise
                except Exception as e:
                    logger.warning(f"Could not send message to {person['name']}: {e}")
                    ChatModalHelper.close_current_chat(page)

                self._wait_with_abort_check(page, DELAY_MS)

            except (WorkflowAbortedException, MissingHebrewNamesException):
                raise
            except Exception as e:
                logger.error(f"Error processing result: {e}")

        return page_messaged

    # --- Connection Request Operations ---

    def _send_connection_requests_on_search_page(self, page, company: str, max_requests: int = 10) -> list[dict]:
        """Send connection requests from search results page."""
        connected_people = []
        company_lower = company.lower()
        page_num = 0
        max_pages = 5

        while len(connected_people) < max_requests and page_num < max_pages:
            page_num += 1
            self.check_abort()
            logger.info(f"Processing page {page_num} ({len(connected_people)}/{max_requests} sent)")

            self._wait_with_abort_check(page, DELAY_MS)

            remaining = max_requests - len(connected_people)
            page_results = self._process_connection_results_page(page, company_lower, connected_people, remaining)
            connected_people.extend(page_results)

            if len(connected_people) >= max_requests:
                break

            if not self._go_to_next_search_page(page):
                break

        return connected_people

    def _process_connection_results_page(self, page, company_lower: str, already_connected: list, max_to_send: int) -> list[dict]:
        """Process search results page to send connection requests."""
        page_connected = []

        results = []
        for selector in LinkedInSelectors.SEARCH_RESULTS:
            results = page.query_selector_all(selector)
            if results:
                break

        if not results:
            return []

        already_connected_urls = {p.get("linkedin_url") for p in already_connected}

        for result in results:
            if len(page_connected) >= max_to_send:
                break

            self.check_abort()

            try:
                person = extract_person_from_search_result(result, company_lower)
                if not person:
                    continue

                if is_vip(person.get("headline", "")):
                    logger.info(f"Skipping {person['name']} - VIP")
                    continue

                if person["linkedin_url"] in already_connected_urls:
                    continue

                # Look for Connect button
                connect_btn = None
                for selector in LinkedInSelectors.CONNECT_BUTTON:
                    connect_btn = result.query_selector(selector)
                    if connect_btn:
                        break

                if not connect_btn:
                    logger.info(f"Skipping {person['name']} - no Connect button")
                    continue

                logger.info(f"Clicking Connect for: {person['name']}")
                connect_btn.click()
                page.wait_for_timeout(DELAY_MS)

                # Check for email verification modal
                page.wait_for_timeout(DELAY_MS // 2)
                send_btn = page.query_selector("button[aria-label='Send without a note'], button:has-text('Send without a note')")
                if send_btn and not send_btn.is_enabled():
                    logger.info(f"Skipping {person['name']} - email verification required")
                    close_btn = page.query_selector("button[aria-label='Dismiss'], button[aria-label='Close']")
                    if close_btn:
                        close_btn.click()
                        page.wait_for_timeout(DELAY_MS // 2)
                    continue

                try:
                    RetryHelper.retry_click(page, LinkedInSelectors.SEND_CONNECTION, f"click Send for {person['name']}")
                    logger.info(f"Connection request sent to: {person['name']}")

                    person["is_connection"] = False
                    person["connection_request_sent"] = True
                    page_connected.append(person)

                except WorkflowAbortedException:
                    raise
                except Exception as e:
                    close_btn = page.query_selector("button[aria-label='Dismiss']")
                    if close_btn:
                        close_btn.click()
                    logger.warning(f"Could not send connection to {person['name']}: {e}")

                self._wait_with_abort_check(page, DELAY_MS)

            except WorkflowAbortedException:
                raise
            except Exception as e:
                logger.error(f"Error sending connection request: {e}")
                try:
                    close_btn = page.query_selector("button[aria-label='Dismiss']")
                    if close_btn:
                        close_btn.click()
                except:
                    pass

        return page_connected

    # --- Reply Checking ---

    async def check_for_replies(self, contacts: list[dict], company: str) -> dict:
        """Check if any contacts have replied."""
        if not self._logged_in:
            return {"replied_contacts": [], "failed_contacts": []}

        if not contacts:
            return {"replied_contacts": [], "failed_contacts": []}

        return await _run_playwright_async(self._check_for_replies_sync, contacts, company)

    def _check_for_replies_sync(self, contacts: list[dict], company: str) -> dict:
        """Synchronous reply checking."""
        if not HAS_PLAYWRIGHT:
            return {"replied_contacts": [], "failed_contacts": []}

        replied_contacts = []
        failed_contacts = []

        try:
            import time
            launch_start = time.time()
            context, page = self._get_or_create_browser()
            launch_time = time.time() - launch_start
            logger.info(f"Browser ready in {launch_time:.1f}s for reply checking")

            # Navigate to feed (or stay if already there)
            current_url = page.url
            if "linkedin.com" not in current_url or "/login" in current_url:
                page.goto("https://www.linkedin.com/feed/", timeout=60000)
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(DELAY_MS)
            else:
                logger.info(f"Already on LinkedIn: {current_url[:50]}")

            # Open messaging panel
            self._open_messaging_panel(page)

            for contact in contacts:
                self.check_abort()
                name = contact.get("name", "")
                if not name:
                    continue

                logger.info(f"Checking for reply from {name}...")

                try:
                    # Search for conversation
                    search_input = None
                    for selector in LinkedInSelectors.MESSAGING_SEARCH:
                        search_input = page.query_selector(selector)
                        if search_input:
                            break

                    if search_input:
                        # Clear and search with proper waits
                        search_input.click()
                        page.wait_for_timeout(300)
                        search_input.fill("")
                        page.wait_for_timeout(500)
                        search_input.fill(name)
                        logger.info(f"Searching for conversation with '{name}', waiting for results...")
                        # Wait longer for search results to load
                        page.wait_for_timeout(3000)
                    else:
                        logger.warning("Could not find messaging search input")

                    # Find and click conversation - try multiple times
                    conversation = None
                    for attempt in range(3):
                        for selector in conversation_selectors(name):
                            conversation = page.query_selector(selector)
                            if conversation:
                                break
                        if conversation:
                            break
                        # Wait and retry
                        page.wait_for_timeout(1000)

                    if not conversation:
                        logger.info(f"No conversation found with {name}")
                        continue

                    logger.info(f"Found conversation with {name}, opening...")
                    conversation.click()
                    # Wait longer for conversation to fully load
                    page.wait_for_timeout(3000)

                    # Check for replies
                    reply_result = page.evaluate(get_reply_check_script(name))
                    has_reply = reply_result.get('hasReply', False) if isinstance(reply_result, dict) else False

                    if has_reply:
                        logger.info(f"Found reply from {name}!")
                        replied_contacts.append(contact)
                    else:
                        logger.info(f"No reply yet from {name}")

                    ChatModalHelper.close_current_chat(page)

                except WorkflowAbortedException:
                    raise
                except Exception as e:
                    logger.warning(f"Error checking reply from {name}: {e}")
                    failed_contacts.append({"name": name, "error": str(e)[:100]})

            return {"replied_contacts": replied_contacts, "failed_contacts": failed_contacts}

        except WorkflowAbortedException:
            raise
        except Exception as e:
            logger.error(f"Error checking for replies: {e}")
            return {"replied_contacts": replied_contacts, "failed_contacts": failed_contacts}
        finally:
            # Don't close browser - keep it open for next operation
            # Just close any open chat overlays
            try:
                if self._page:
                    ChatModalHelper.close_all_overlays(self._page)
            except:
                pass

    def _open_messaging_panel(self, page):
        """Open the messaging panel if not already open."""
        logger.info("Opening messaging panel...")

        # Check if already open
        for selector in LinkedInSelectors.MESSAGING_PANEL_OPEN:
            if page.query_selector(selector):
                logger.info("Messaging panel already open")
                # Even if open, wait for conversations to load
                page.wait_for_timeout(3000)
                return

        # Try to click messaging button
        clicked = False
        for selector in LinkedInSelectors.MESSAGING_BUTTON:
            btn = page.query_selector(selector)
            if btn:
                logger.info(f"Clicking messaging button: {selector}")
                btn.click()
                clicked = True
                break

        # Try minimized version if main button didn't work
        if not clicked:
            for selector in LinkedInSelectors.MESSAGING_MINIMIZED:
                minimized = page.query_selector(selector)
                if minimized:
                    logger.info(f"Clicking minimized messaging: {selector}")
                    minimized.click()
                    clicked = True
                    break

        if not clicked:
            logger.warning("Could not find messaging button")
            return

        # Wait for panel to open with longer timeout
        try:
            page.wait_for_selector(
                ".msg-overlay-list-bubble--is-open, .msg-overlay-list-bubble__conversations-container, aside[data-test-id='msg-overlay']",
                timeout=15000
            )
            logger.info("Messaging panel opened, waiting for conversations to load...")
            # Give LinkedIn time to load conversation list - this is critical!
            page.wait_for_timeout(5000)
            logger.info("Conversations should be loaded now")
        except Exception as e:
            logger.warning(f"Messaging panel did not appear: {e}")

    # --- Legacy/Compatibility Methods ---

    async def search_people(self, keywords: str = None, current_company: list[str] = None, limit: int = 10) -> list[dict]:
        """Search for 2nd degree people at a company."""
        if not self._logged_in:
            return []
        return await _run_playwright_async(self._search_2nd_degree_sync, keywords, limit)

    def _search_2nd_degree_sync(self, company: str, limit: int) -> list[dict]:
        """Synchronous 2nd degree search."""
        # Simplified - use the combined search instead
        result = self._search_company_all_degrees_sync(company, limit, None, False)
        return result.get("second_degree", [])

    async def search_connections_by_company(self, company: str) -> list[dict]:
        """Search for 1st degree connections at a company."""
        if not self._logged_in:
            return []
        result = await self.search_company_all_degrees(company, 15, None, True)
        return result.get("first_degree", [])

    async def get_connections(self, limit: int = 100) -> list[dict]:
        """Get the user's connections."""
        if not self._logged_in:
            return []
        return await _run_playwright_async(self._get_connections_sync, limit)

    def _get_connections_sync(self, limit: int) -> list[dict]:
        """Synchronous get connections."""
        if not HAS_PLAYWRIGHT:
            return []

        try:
            context, page = self._get_or_create_browser()

            page.goto("https://www.linkedin.com/mynetwork/invite-connect/connections/", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            page.wait_for_timeout(1000)

            connections = []
            results = []
            for selector in LinkedInSelectors.CONNECTION_CARDS:
                results = page.query_selector_all(selector)
                if results:
                    break

            for card in results[:limit]:
                conn = extract_connection_from_card(card)
                if conn:
                    connections.append(conn)

            # Don't close browser
            return connections

        except Exception as e:
            logger.error(f"Failed to get connections: {e}")
            return []

    async def send_message(self, message: str, public_id: str = None, profile_url: str = None, urn_id: str = None) -> bool:
        """Send a message to a connection."""
        if not self._logged_in:
            return False

        if not public_id and profile_url and "/in/" in profile_url:
            public_id = profile_url.split("/in/")[1].rstrip("/").split("?")[0]

        if not public_id:
            return False

        return await _run_playwright_async(self._send_message_sync, public_id, message)

    def _send_message_sync(self, public_id: str, message: str) -> bool:
        """Synchronous send message."""
        if not HAS_PLAYWRIGHT:
            return False

        try:
            context, page = self._get_or_create_browser()

            page.goto(f"https://www.linkedin.com/in/{public_id}/")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(500)

            message_btn = page.query_selector("button:has-text('Message')")
            if not message_btn:
                return False

            message_btn.click()
            page.wait_for_timeout(1000)

            message_input = page.query_selector("div.msg-form__contenteditable")
            if message_input:
                message_input.fill(message)
                page.wait_for_timeout(500)

                send_btn = page.query_selector("button.msg-form__send-button")
                if send_btn:
                    send_btn.click()
                    page.wait_for_timeout(2000)
                    ChatModalHelper.close_current_chat(page)
                    return True

            return False

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def send_connection_request(self, public_id: str, message: str = None) -> bool:
        """Send a connection request."""
        if not self._logged_in:
            return False
        return await _run_playwright_async(self._send_connection_request_sync, public_id, message)

    def _send_connection_request_sync(self, public_id: str, message: str = None) -> bool:
        """Synchronous send connection request."""
        if not HAS_PLAYWRIGHT:
            return False

        try:
            context, page = self._get_or_create_browser()

            page.goto(f"https://www.linkedin.com/in/{public_id}/")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(500)

            connect_btn = page.query_selector("button:has-text('Connect')")
            if not connect_btn:
                return False

            connect_btn.click()
            page.wait_for_timeout(1000)

            if message:
                add_note = page.query_selector("button:has-text('Add a note')")
                if add_note:
                    add_note.click()
                    page.wait_for_timeout(500)
                    note_input = page.query_selector("textarea#custom-message")
                    if note_input:
                        note_input.fill(message[:300])
                        page.wait_for_timeout(500)

            send_btn = page.query_selector("button:has-text('Send')")
            if send_btn:
                send_btn.click()
                page.wait_for_timeout(2000)
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to send connection request: {e}")
            return False


def get_linkedin_client() -> LinkedInClient:
    """Get the global LinkedIn client instance."""
    return LinkedInClient.get_instance()
