"""
Browser utilities for LinkedIn automation.

Contains browser context management, retry logic, and chat modal helpers.
"""

import os
import sys
from pathlib import Path
from contextlib import contextmanager

from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_browser_data_path() -> Path:
    """
    Get the path for browser data (persistent context).

    In desktop mode (frozen exe), uses LOCALAPPDATA/JobiAI/browser_context/
    In development mode, uses linkedin_data/browser_context/
    """
    if getattr(sys, 'frozen', False):
        # Desktop mode - store in LOCALAPPDATA
        data_dir = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'JobiAI'
        path = data_dir / 'browser_context'
        logger.info(f"Desktop mode - browser data path: {path}")
        return path
    else:
        # Development mode
        path = Path("linkedin_data/browser_context")
        logger.info(f"Development mode - browser data path: {path}")
        return path


# Path to store browser data (persistent context)
# Note: This is evaluated at import time, which is fine since
# desktop.py sets up the environment before importing anything
BROWSER_DATA_PATH = get_browser_data_path()

# Speed mode - set to false for more human-like delays (safer)
FAST_MODE = os.getenv("FAST_MODE", "true").lower() == "true"

# Delay multiplier based on mode
DELAY_MS = 300 if FAST_MODE else 1000

# Retry delays in seconds: 0.2, 0.5, 1.5, 2.0
RETRY_DELAYS = [0.2, 0.5, 1.5, 2.0]


def ensure_browser_data_dir():
    """Ensure browser data directory exists."""
    BROWSER_DATA_PATH.mkdir(parents=True, exist_ok=True)


def get_browser_visibility() -> bool:
    """Get browser visibility setting from app settings."""
    try:
        from app.settings import get_settings
        return get_settings().browser_visible
    except Exception:
        # Settings not initialized (dev mode or not desktop app)
        return True  # Default to visible


def get_browser_args(viewport: dict = None, maximized: bool = True, hidden: bool = None) -> dict:
    """
    Get standard browser launch arguments.

    Args:
        viewport: Optional viewport size dict with width/height
        maximized: If True, use maximized window (default: True)
        hidden: If True, position window off-screen. If None, uses app settings.

    Returns:
        Dict of arguments for launch_persistent_context
    """
    # Determine if browser should be hidden
    if hidden is None:
        hidden = not get_browser_visibility()

    if hidden:
        # Position window far off-screen (not headless - that's detected by LinkedIn)
        return {
            "headless": False,
            "viewport": {"width": 1280, "height": 720},
            "args": ["--window-position=-32000,-32000", "--window-size=1300,750"],
        }

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
        LinkedIn 2026 uses Shadow DOM for messaging UI.
        """
        logger.info("Closing any open message overlays...")
        page.wait_for_timeout(500)

        try:
            closed_count = page.evaluate("""
                () => {
                    let closedCount = 0;

                    // Helper to search in shadow DOM
                    function findAllInShadowDOM(selector) {
                        const results = [];
                        document.querySelectorAll(selector).forEach(el => results.push(el));
                        const allElements = document.querySelectorAll('*');
                        for (const el of allElements) {
                            if (el.shadowRoot) {
                                el.shadowRoot.querySelectorAll(selector).forEach(shadowEl => results.push(shadowEl));
                            }
                        }
                        return results;
                    }

                    // LinkedIn 2026: Find all dialogs in shadow DOM and close them
                    // The close button is .msg-overlay-bubble-header__control but NOT .msg-overlay-conversation-bubble__expand-btn
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        if (el.shadowRoot) {
                            const dialogs = el.shadowRoot.querySelectorAll('[role="dialog"]');
                            for (const dialog of dialogs) {
                                const headerControls = dialog.querySelectorAll('.msg-overlay-bubble-header__control');
                                for (const btn of headerControls) {
                                    // Close button doesn't have expand-btn class (that's the minimize button)
                                    if (!btn.classList.contains('msg-overlay-conversation-bubble__expand-btn')) {
                                        try {
                                            btn.click();
                                            closedCount++;
                                        } catch (e) {}
                                    }
                                }
                            }
                        }
                    }

                    // Fallback: Find close buttons by aria-label (older LinkedIn versions)
                    const closeButtons = findAllInShadowDOM('button[aria-label*="Close"]');
                    for (const btn of closeButtons) {
                        try {
                            btn.click();
                            closedCount++;
                        } catch (e) {}
                    }

                    return closedCount;
                }
            """)

            if closed_count > 0:
                logger.info(f"Closed {closed_count} message overlay(s)")
                page.wait_for_timeout(500)
            else:
                logger.info("No open message overlays found")

            # Press Escape as backup
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
            # LinkedIn 2026 uses Shadow DOM for messaging UI
            # NOTE: LinkedIn removed aria-label from close button, so we identify it by class
            closed = page.evaluate("""
                () => {
                    // Helper to search in shadow DOM
                    function findInShadowDOM(selector) {
                        let result = document.querySelector(selector);
                        if (result) return result;
                        const allElements = document.querySelectorAll('*');
                        for (const el of allElements) {
                            if (el.shadowRoot) {
                                result = el.shadowRoot.querySelector(selector);
                                if (result) return result;
                            }
                        }
                        return null;
                    }

                    function findAllInShadowDOM(selector) {
                        const results = [];
                        document.querySelectorAll(selector).forEach(el => results.push(el));
                        const allElements = document.querySelectorAll('*');
                        for (const el of allElements) {
                            if (el.shadowRoot) {
                                el.shadowRoot.querySelectorAll(selector).forEach(shadowEl => results.push(shadowEl));
                            }
                        }
                        return results;
                    }

                    // LinkedIn 2026: Find dialog in shadow DOM and click close button
                    // The close button is .msg-overlay-bubble-header__control but NOT .msg-overlay-conversation-bubble__expand-btn
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        if (el.shadowRoot) {
                            const dialog = el.shadowRoot.querySelector('[role="dialog"]');
                            if (dialog) {
                                const headerControls = dialog.querySelectorAll('.msg-overlay-bubble-header__control');
                                for (const btn of headerControls) {
                                    // Close button doesn't have expand-btn class (that's the minimize button)
                                    if (!btn.classList.contains('msg-overlay-conversation-bubble__expand-btn')) {
                                        btn.click();
                                        return true;
                                    }
                                }
                            }
                        }
                    }

                    // Fallback: Try aria-label (older LinkedIn versions)
                    const closeButtons = findAllInShadowDOM('button[aria-label*="Close"]');
                    for (const btn of closeButtons) {
                        try {
                            btn.click();
                            return true;
                        } catch (e) {}
                    }

                    // Fallback: Try legacy selectors
                    const activeBubble = findInShadowDOM('.msg-overlay-conversation-bubble--is-active') ||
                                        findInShadowDOM('.msg-overlay-conversation-bubble');
                    if (activeBubble) {
                        const headerControls = activeBubble.querySelectorAll('.msg-overlay-bubble-header__control');
                        for (const btn of headerControls) {
                            if (!btn.classList.contains('msg-overlay-conversation-bubble__expand-btn')) {
                                btn.click();
                                return true;
                            }
                        }
                    }

                    return false;
                }
            """)

            page.wait_for_timeout(500)

            # Press Escape as backup
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
            # LinkedIn 2026 uses Shadow DOM for messaging UI
            result = page.evaluate("""
                () => {
                    const selectors = [
                        '[role="dialog"]',
                        '.msg-overlay-conversation-bubble',
                        '.msg-form',
                        '[role="textbox"]',
                        '.msg-overlay-bubble-header',
                        '.msg-s-message-list-container',
                        '.artdeco-modal'
                    ];

                    const debugInfo = {
                        lightDomChecked: true,
                        shadowRootsFound: 0,
                        shadowHostClasses: []
                    };

                    // Check light DOM first
                    for (const sel of selectors) {
                        if (document.querySelector(sel)) {
                            return {found: true, selector: sel, location: 'light-dom', debug: debugInfo};
                        }
                    }

                    // Recursive function to search shadow DOM at any depth
                    const searchShadowDOM = (root, depth = 0) => {
                        if (depth > 5) return null; // Prevent infinite recursion

                        const elements = root.querySelectorAll('*');
                        for (const el of elements) {
                            if (el.shadowRoot) {
                                debugInfo.shadowRootsFound++;
                                debugInfo.shadowHostClasses.push(el.className.substring(0, 50));

                                // Check this shadow root
                                for (const sel of selectors) {
                                    const found = el.shadowRoot.querySelector(sel);
                                    if (found) {
                                        return {selector: sel, depth: depth};
                                    }
                                }

                                // Search nested shadow roots
                                const nested = searchShadowDOM(el.shadowRoot, depth + 1);
                                if (nested) return nested;
                            }
                        }
                        return null;
                    };

                    const shadowResult = searchShadowDOM(document);
                    if (shadowResult) {
                        return {
                            found: true,
                            selector: shadowResult.selector,
                            location: 'shadow-dom-depth-' + shadowResult.depth,
                            debug: debugInfo
                        };
                    }

                    return {found: false, selector: null, debug: debugInfo};
                }
            """)
            if result.get('found'):
                logger.info(f"Modal detected via: {result.get('selector')} in {result.get('location')}")
            else:
                debug = result.get('debug', {})
                logger.info(f"Modal NOT detected - shadow roots found: {debug.get('shadowRootsFound', 0)}, hosts: {debug.get('shadowHostClasses', [])[:3]}")
            return result.get('found', False)
        except Exception as e:
            logger.warning(f"Error checking modal: {e}")
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


def hide_browser_window():
    """Move the browser window off-screen (Windows only)."""
    try:
        import win32gui
        import win32con

        def hide_chromium(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            if "Chromium" in title or "LinkedIn" in title:
                # Move window far off-screen
                win32gui.SetWindowPos(
                    hwnd, None,
                    -32000, -32000,  # Off-screen position
                    0, 0,  # Keep current size
                    win32con.SWP_NOSIZE | win32con.SWP_NOZORDER
                )
                return False
            return True

        win32gui.EnumWindows(hide_chromium, None)
        logger.info("Browser window hidden (moved off-screen)")
    except Exception as e:
        logger.debug(f"Could not hide browser window: {e}")


def show_browser_window():
    """Restore the browser window to visible position (Windows only)."""
    try:
        import win32gui
        import win32con

        def show_chromium(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            if "Chromium" in title or "LinkedIn" in title:
                # Move window to visible position and restore
                win32gui.SetWindowPos(
                    hwnd, None,
                    100, 100,  # Visible position
                    0, 0,  # Keep current size
                    win32con.SWP_NOSIZE | win32con.SWP_NOZORDER
                )
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                return False
            return True

        win32gui.EnumWindows(show_chromium, None)
        logger.info("Browser window shown")
    except Exception as e:
        logger.debug(f"Could not show browser window: {e}")
