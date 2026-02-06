"""
Browser installation utility for desktop mode.

Handles downloading Playwright's Chromium browser on first run.
In desktop mode, the browser is stored in LOCALAPPDATA/JobiAI/browsers/
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_browsers_path() -> Path:
    """Get the path where Playwright browsers should be stored."""
    if getattr(sys, 'frozen', False):
        # Desktop mode - store in LOCALAPPDATA
        data_dir = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'JobiAI'
    else:
        # Development mode - use default Playwright location
        return Path.home() / '.cache' / 'ms-playwright'

    return data_dir / 'browsers'


def set_browser_path_env():
    """Set the PLAYWRIGHT_BROWSERS_PATH environment variable."""
    browsers_path = get_browsers_path()
    browsers_path.mkdir(parents=True, exist_ok=True)
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(browsers_path)
    logger.info(f"Playwright browsers path set to: {browsers_path}")


def is_browser_installed() -> Tuple[bool, Optional[str]]:
    """
    Check if Playwright Chromium browser is installed.

    Returns:
        Tuple of (is_installed, error_message)
    """
    try:
        # Set the browser path first
        set_browser_path_env()

        from playwright.sync_api import sync_playwright

        # Try to get the executable path
        with sync_playwright() as p:
            # This will raise an exception if browser not installed
            executable = p.chromium.executable_path
            if Path(executable).exists():
                logger.info(f"Chromium browser found at: {executable}")
                return True, None
            else:
                return False, f"Browser executable not found at {executable}"

    except Exception as e:
        error_msg = str(e)
        if "Executable doesn't exist" in error_msg:
            return False, "Chromium browser not installed"
        return False, f"Error checking browser: {error_msg}"


def install_browser(progress_callback=None) -> Tuple[bool, str]:
    """
    Install Playwright Chromium browser.

    Args:
        progress_callback: Optional callback function(message: str) for progress updates

    Returns:
        Tuple of (success, message)
    """
    def log_progress(msg: str):
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    try:
        # Set browser path
        set_browser_path_env()
        browsers_path = get_browsers_path()

        log_progress(f"Installing Chromium browser to {browsers_path}...")

        # Run playwright install chromium
        # Use the playwright module's install command
        result = subprocess.run(
            [sys.executable, '-m', 'playwright', 'install', 'chromium'],
            capture_output=True,
            text=True,
            env={**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': str(browsers_path)}
        )

        if result.returncode == 0:
            log_progress("Chromium browser installed successfully!")
            return True, "Browser installed successfully"
        else:
            error = result.stderr or result.stdout
            log_progress(f"Installation failed: {error}")
            return False, f"Installation failed: {error}"

    except Exception as e:
        error_msg = f"Error installing browser: {e}"
        log_progress(error_msg)
        return False, error_msg


def ensure_browser_installed(show_notification=None) -> bool:
    """
    Ensure Playwright browser is installed, installing if necessary.

    Args:
        show_notification: Optional callback(title, message) to show notifications

    Returns:
        True if browser is ready, False if installation failed
    """
    installed, error = is_browser_installed()

    if installed:
        return True

    logger.info(f"Browser not installed: {error}")

    # Show notification that we're downloading
    if show_notification:
        show_notification(
            "JobiAI",
            "Downloading browser for LinkedIn automation...\nThis may take a few minutes on first run."
        )

    # Install browser
    success, message = install_browser()

    if success:
        if show_notification:
            show_notification("JobiAI", "Browser ready!")
        return True
    else:
        if show_notification:
            show_notification("JobiAI", f"Browser installation failed: {message}")
        return False
