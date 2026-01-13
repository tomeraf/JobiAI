"""
Browser utilities for LinkedIn automation.

Contains browser context management, retry logic, and chat modal helpers.
"""

import os
from pathlib import Path
from contextlib import contextmanager

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Path to store browser data (persistent context)
BROWSER_DATA_PATH = Path("linkedin_data/browser_context")

# Speed mode - set to false for more human-like delays (safer)
FAST_MODE = os.getenv("FAST_MODE", "true").lower() == "true"

# Delay multiplier based on mode
DELAY_MS = 300 if FAST_MODE else 1000

# Retry delays in seconds: 0.2, 0.5, 1.5, 2.0
RETRY_DELAYS = [0.2, 0.5, 1.5, 2.0]


def ensure_browser_data_dir():
    """Ensure browser data directory exists."""
    BROWSER_DATA_PATH.mkdir(parents=True, exist_ok=True)


def get_browser_args(viewport: dict = None, maximized: bool = False) -> dict:
    """
    Get standard browser launch arguments.

    Args:
        viewport: Optional viewport size dict with width/height
        maximized: If True, use maximized window (for login flow)

    Returns:
        Dict of arguments for launch_persistent_context
    """
    if maximized:
        return {
            "headless": False,
            "no_viewport": True,
            "args": ["--start-maximized"],
        }

    return {
        "headless": False,
        "viewport": viewport or {"width": 1280, "height": 720},
        "args": ["--window-size=1300,750", "--window-position=100,100"],
    }


class RetryHelper:
    """Helper class for retry logic with progressive delays."""

    @staticmethod
    def retry_click(page, selectors: list[str], action_name: str, delay_ms: int = DELAY_MS) -> bool:
        """
        Retry clicking an element with progressive delays.

        Args:
            page: Playwright page object
            selectors: List of CSS selectors to try
            action_name: Human-readable name for logging
            delay_ms: Delay after successful click

        Returns:
            True if click succeeded

        Raises:
            Exception if all retries fail
        """
        for attempt, delay in enumerate([0] + RETRY_DELAYS):
            if delay > 0:
                logger.info(f"Retry {attempt}/{len(RETRY_DELAYS)} for {action_name} - waiting {delay}s...")
                page.wait_for_timeout(int(delay * 1000))

            for selector in selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        logger.info(f"Found element for '{action_name}' with selector: {selector}")
                        element.click()
                        page.wait_for_timeout(delay_ms)
                        return True
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

            if delay == 0:
                logger.info(f"First attempt for '{action_name}' failed, starting retries...")

        error_msg = f"Failed to {action_name} after {len(RETRY_DELAYS)} retries"
        logger.error(error_msg)
        raise Exception(error_msg)

    @staticmethod
    def retry_find(page, selectors: list[str], action_name: str):
        """
        Retry finding an element with progressive delays.

        Args:
            page: Playwright page object
            selectors: List of CSS selectors to try
            action_name: Human-readable name for logging

        Returns:
            The found element

        Raises:
            Exception if all retries fail
        """
        for attempt, delay in enumerate([0] + RETRY_DELAYS):
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

        error_msg = f"Failed to {action_name} after {len(RETRY_DELAYS)} retries"
        logger.error(error_msg)
        raise Exception(error_msg)

    @staticmethod
    def retry_find_in_element(page, element, selectors: list[str], action_name: str):
        """
        Retry finding an element within a parent element.

        Args:
            page: Playwright page object (for wait_for_timeout)
            element: Parent element to search within
            selectors: List of CSS selectors to try
            action_name: Human-readable name for logging

        Returns:
            The found element, or None if not found
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

        logger.debug(f"Could not find element for '{action_name}' after retries")
        return None

    @staticmethod
    def retry_click_in_element(page, element, selectors: list[str], action_name: str, delay_ms: int = DELAY_MS) -> bool:
        """
        Retry clicking an element within a parent element.

        Args:
            page: Playwright page object
            element: Parent element to search within
            selectors: List of CSS selectors to try
            action_name: Human-readable name for logging
            delay_ms: Delay after successful click

        Returns:
            True if click succeeded, False otherwise
        """
        found = RetryHelper.retry_find_in_element(page, element, selectors, action_name)
        if found:
            found.click()
            page.wait_for_timeout(delay_ms)
            return True
        return False


class ChatModalHelper:
    """Helper class for chat modal operations."""

    @staticmethod
    def close_all_overlays(page):
        """
        Close all open message dialogs/overlays on LinkedIn.

        Uses JavaScript execution for reliability with LinkedIn's dynamic DOM.
        LinkedIn's close button does NOT have aria-label - identify by class and SVG icon.
        """
        logger.info("Closing any open message overlays...")
        page.wait_for_timeout(500)

        try:
            closed_count = page.evaluate("""
                () => {
                    let closedCount = 0;

                    // Find all conversation bubbles (both active and inactive)
                    const bubbles = document.querySelectorAll('.msg-overlay-conversation-bubble');
                    for (const bubble of bubbles) {
                        // Find header control buttons
                        const headerControls = bubble.querySelectorAll('.msg-overlay-bubble-header__control');
                        for (const btn of headerControls) {
                            // Check if button contains close icon SVG
                            if (btn.innerHTML.includes('close')) {
                                try {
                                    btn.click();
                                    closedCount++;
                                } catch (e) {}
                                break; // Only click one close button per bubble
                            }
                        }
                    }

                    return closedCount;
                }
            """)

            if closed_count > 0:
                logger.info(f"Closed {closed_count} message overlay(s)")
                page.wait_for_timeout(500)
            else:
                logger.info("No open message overlays found")

            # Double-check if any bubbles still exist
            still_open = page.evaluate("""
                () => !!document.querySelector('.msg-overlay-conversation-bubble')
            """)
            if still_open:
                logger.info("Overlays still detected, pressing Escape")
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)

        except Exception as e:
            logger.warning(f"JavaScript overlay close failed: {e}")
            # Fallback: press Escape
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except:
                pass

    @staticmethod
    def close_current_chat(page):
        """Close the currently open chat modal by clicking the X button."""
        try:
            # Use JavaScript to find and click the close button
            # LinkedIn's close button does NOT have aria-label, we identify it by:
            # 1. It's inside .msg-overlay-conversation-bubble--is-active
            # 2. It has class .msg-overlay-bubble-header__control
            # 3. Its SVG has data-test-icon="close" or contains "close" in innerHTML
            closed = page.evaluate("""
                () => {
                    // Find the active conversation bubble
                    const activeBubble = document.querySelector('.msg-overlay-conversation-bubble--is-active');
                    if (!activeBubble) {
                        // Try any conversation bubble
                        const anyBubble = document.querySelector('.msg-overlay-conversation-bubble');
                        if (!anyBubble) return false;

                        const headerControls = anyBubble.querySelectorAll('.msg-overlay-bubble-header__control');
                        for (const btn of headerControls) {
                            if (btn.innerHTML.includes('close')) {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }

                    // Find header control buttons in the active bubble
                    const headerControls = activeBubble.querySelectorAll('.msg-overlay-bubble-header__control');

                    // Look for the close button by checking SVG icon
                    for (const btn of headerControls) {
                        // Check if the button contains a close icon SVG
                        if (btn.innerHTML.includes('close')) {
                            btn.click();
                            return true;
                        }
                    }

                    // Fallback: the close button is usually the last header control
                    if (headerControls.length >= 2) {
                        headerControls[headerControls.length - 1].click();
                        return true;
                    }

                    return false;
                }
            """)

            page.wait_for_timeout(500)

            # Verify chat is closed
            still_open = page.evaluate("""
                () => !!document.querySelector('.msg-overlay-conversation-bubble--is-active')
            """)

            if still_open:
                # Try clicking outside the modal to close it
                logger.info("Chat still open, trying to click outside to close")
                try:
                    # Click on the search results area to dismiss the chat
                    page.click("body", position={"x": 400, "y": 300}, force=True)
                    page.wait_for_timeout(300)
                except Exception:
                    pass

                # Check again
                still_open = page.evaluate("""
                    () => !!document.querySelector('.msg-overlay-conversation-bubble--is-active')
                """)

                if still_open:
                    # Last resort - press Escape multiple times
                    for i in range(3):
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(200)

            return True
        except Exception as e:
            logger.warning(f"Error closing chat: {e}")
            # Try Escape as last resort
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except:
                pass
            return False

    @staticmethod
    def is_modal_open(page) -> bool:
        """Check if a chat modal is currently open."""
        try:
            return page.evaluate("""
                () => !!(document.querySelector('[role="dialog"]') ||
                         document.querySelector('.msg-overlay-conversation-bubble'))
            """)
        except:
            return False


def bring_browser_to_front():
    """Bring the Chromium browser window to the foreground (Windows only)."""
    try:
        import win32gui
        import win32con
        import time
        time.sleep(0.5)

        def bring_chromium_to_front(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            if "Chromium" in title or "LinkedIn" in title:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                return False
            return True

        win32gui.EnumWindows(bring_chromium_to_front, None)
    except Exception as e:
        logger.debug(f"Could not bring window to front: {e}")
