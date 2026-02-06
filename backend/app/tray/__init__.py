"""
JobiAI System Tray Module

Provides system tray functionality for the desktop application.
"""

from app.tray.app import TrayApp
from app.tray.browser_installer import (
    set_browser_path_env,
    is_browser_installed,
    install_browser,
    ensure_browser_installed,
)

__all__ = [
    'TrayApp',
    'set_browser_path_env',
    'is_browser_installed',
    'install_browser',
    'ensure_browser_installed',
]
