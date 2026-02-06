"""
Main System Tray Application

Orchestrates the FastAPI server, browser, and system tray icon.
"""

import threading
import webbrowser
import sys
import os
from pathlib import Path
from typing import Optional

import pystray
from PIL import Image, ImageDraw
import uvicorn

from app.settings import AppSettings, init_settings, save_settings, get_settings
from app.utils.logger import get_logger
from app.utils.port_finder import get_backend_port

logger = get_logger(__name__)


def create_default_icon(size: int = 64, color: str = '#4A90D9') -> Image.Image:
    """Create a simple default icon (blue circle with J)."""
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Draw circle background
    margin = 2
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=color
    )

    # Draw "J" letter
    font_size = size // 2
    # Use default font (no external dependency)
    text = "J"
    # Get text bounding box for centering
    bbox = draw.textbbox((0, 0), text)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - 2  # Slight adjustment for visual centering
    draw.text((x, y), text, fill='white')

    return image


def load_icon(name: str = 'default', assets_dir: Optional[Path] = None) -> Image.Image:
    """Load an icon from assets or create a default one."""
    if assets_dir:
        icon_path = assets_dir / f'icon_{name}.png'
        if icon_path.exists():
            try:
                return Image.open(icon_path)
            except Exception as e:
                logger.warning(f"Failed to load icon {icon_path}: {e}")

        # Try .ico file
        ico_path = assets_dir / f'icon.ico'
        if ico_path.exists():
            try:
                return Image.open(ico_path)
            except Exception as e:
                logger.warning(f"Failed to load icon {ico_path}: {e}")

    # Return default generated icon
    return create_default_icon()


class TrayApp:
    """
    System Tray Application for JobiAI.

    Manages:
    - FastAPI server running in a background thread
    - System tray icon with menu
    - Browser visibility control
    - Settings persistence
    """

    def __init__(self, data_dir: Path, app_dir: Optional[Path] = None):
        """
        Initialize the tray application.

        Args:
            data_dir: Directory for user data (settings, database)
            app_dir: Directory containing app assets (icons, frontend)
        """
        self.data_dir = data_dir
        self.app_dir = app_dir or Path(__file__).parent.parent.parent

        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Load settings
        self.settings = init_settings(self.data_dir)

        # Find available port (Windows may block some ports)
        try:
            available_port = get_backend_port()
            if available_port != self.settings.port:
                logger.info(f"Port {self.settings.port} unavailable, using {available_port}")
                self.settings.port = available_port
                save_settings()
        except RuntimeError as e:
            logger.error(f"Failed to find available port: {e}")

        # Server state
        self.server_thread: Optional[threading.Thread] = None
        self.server: Optional[uvicorn.Server] = None
        self._server_started = threading.Event()

        # Tray state
        self.icon: Optional[pystray.Icon] = None
        self._running = False

        logger.info(f"TrayApp initialized - data_dir: {self.data_dir}, app_dir: {self.app_dir}")

    def run(self) -> None:
        """Start the application (blocking)."""
        logger.info("Starting JobiAI Desktop App...")

        # Check and install browser if needed (first run may download ~200MB)
        self._ensure_browser_installed()

        # Start FastAPI server in background
        self._start_server()

        # Wait for server to be ready
        if not self._server_started.wait(timeout=30):
            logger.error("Server failed to start within 30 seconds")
            return

        logger.info(f"Server started on port {self.settings.port}")

        # Open browser on first run
        if self.settings.first_run:
            self.settings.first_run = False
            save_settings()
            self.open_ui()

        # Create and run tray icon (this blocks)
        self._running = True
        self._create_tray_icon()

        logger.info("TrayApp exiting...")

    def _start_server(self) -> None:
        """Start the FastAPI server in a background thread."""
        # Import here to ensure proper module loading in PyInstaller bundle
        from app.main import app as fastapi_app

        def run_server():
            try:
                config = uvicorn.Config(
                    fastapi_app,  # Pass app object directly, not string
                    host='127.0.0.1',
                    port=self.settings.port,
                    log_level='warning',
                    access_log=False,
                )
                self.server = uvicorn.Server(config)

                # Signal that we're about to start
                self._server_started.set()

                # This blocks until server stops
                self.server.run()
            except Exception as e:
                logger.error(f"Server error: {e}")
                self._server_started.set()  # Unblock even on error

        self.server_thread = threading.Thread(target=run_server, daemon=True, name='uvicorn-server')
        self.server_thread.start()

    def _ensure_browser_installed(self) -> None:
        """Check and install Playwright browser if needed."""
        try:
            from app.tray.browser_installer import is_browser_installed, install_browser

            installed, error = is_browser_installed()
            if installed:
                logger.info("Playwright browser is already installed")
                return

            logger.info(f"Browser not installed: {error}")
            logger.info("Downloading Chromium browser... (this may take a few minutes)")

            # Show a notification if we can
            try:
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(
                    "JobiAI",
                    "Downloading browser for first run...",
                    duration=5,
                    threaded=True
                )
            except Exception:
                pass  # Notification is optional

            # Install browser
            success, message = install_browser()
            if success:
                logger.info("Browser installed successfully")
            else:
                logger.error(f"Browser installation failed: {message}")
                logger.error("LinkedIn features may not work without the browser")

        except Exception as e:
            logger.error(f"Error checking/installing browser: {e}")

    def _create_tray_icon(self) -> None:
        """Create and run the system tray icon."""
        # Load icon
        assets_dir = self.app_dir / 'assets'
        icon_image = load_icon('default', assets_dir)

        # Create menu
        menu = pystray.Menu(
            pystray.MenuItem('Open JobiAI', self.open_ui, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('LinkedIn Login', self.open_linkedin_login),
            pystray.MenuItem(
                'Show Browser',
                self.toggle_browser_visibility,
                checked=lambda item: self.settings.browser_visible
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                'Start with Windows',
                self.toggle_autostart,
                checked=lambda item: self.settings.auto_start
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Exit', self.exit_app),
        )

        # Create and run icon
        self.icon = pystray.Icon(
            'JobiAI',
            icon_image,
            'JobiAI - LinkedIn Job Bot',
            menu=menu
        )

        logger.info("System tray icon created")
        self.icon.run()  # This blocks

    def open_ui(self, icon=None, item=None) -> None:
        """Open the web UI in the default browser."""
        url = f'http://localhost:{self.settings.port}'
        logger.info(f"Opening UI at {url}")
        webbrowser.open(url)

    def open_linkedin_login(self, icon=None, item=None) -> None:
        """Open LinkedIn login in a visible browser."""
        logger.info("Opening LinkedIn login browser...")
        # Import here to avoid circular imports
        from app.services.linkedin.client import get_linkedin_client

        # Temporarily make browser visible for login
        old_visible = self.settings.browser_visible
        self.settings.browser_visible = True

        try:
            client = get_linkedin_client()
            # This will open the browser for manual login
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(client.login_with_browser())
            finally:
                loop.close()
        finally:
            # Restore visibility setting
            self.settings.browser_visible = old_visible

    def toggle_browser_visibility(self, icon=None, item=None) -> None:
        """Toggle browser visibility setting."""
        self.settings.browser_visible = not self.settings.browser_visible
        save_settings()
        logger.info(f"Browser visibility set to: {self.settings.browser_visible}")

        # Update icon menu to reflect new state
        if self.icon:
            self.icon.update_menu()

    def toggle_autostart(self, icon=None, item=None) -> None:
        """Toggle Windows auto-start setting."""
        self.settings.auto_start = not self.settings.auto_start
        save_settings()
        logger.info(f"Auto-start set to: {self.settings.auto_start}")

        # Update Windows registry
        try:
            from app.tray.autostart import set_autostart
            set_autostart(self.settings.auto_start)
        except Exception as e:
            logger.warning(f"Failed to update autostart: {e}")

        # Update icon menu
        if self.icon:
            self.icon.update_menu()

    def exit_app(self, icon=None, item=None) -> None:
        """Exit the application cleanly."""
        logger.info("Exit requested...")
        self._running = False

        # Close browser if open
        try:
            from app.services.linkedin.client import get_linkedin_client
            client = get_linkedin_client()
            client.close_browser()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")

        # Stop server
        if self.server:
            self.server.should_exit = True

        # Stop tray icon
        if self.icon:
            self.icon.stop()

        logger.info("JobiAI Desktop App stopped")
