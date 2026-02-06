"""
Windows Auto-Start Management

Manages the Windows registry entry for starting JobiAI on login.
"""

import sys
import winreg
from pathlib import Path
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Registry key for auto-start programs
AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "JobiAI"


def get_executable_path() -> str:
    """Get the path to the current executable."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return sys.executable
    else:
        # Running as script - return python with script path
        return f'"{sys.executable}" "{Path(__file__).parent.parent / "desktop.py"}"'


def is_autostart_enabled() -> bool:
    """Check if auto-start is currently enabled."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            AUTOSTART_KEY,
            0,
            winreg.KEY_READ
        )
        try:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception as e:
        logger.warning(f"Failed to check autostart status: {e}")
        return False


def set_autostart(enabled: bool) -> bool:
    """
    Enable or disable auto-start with Windows.

    Args:
        enabled: True to enable, False to disable

    Returns:
        True if successful, False otherwise
    """
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            AUTOSTART_KEY,
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_READ
        )

        try:
            if enabled:
                exe_path = get_executable_path()
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
                logger.info(f"Auto-start enabled: {exe_path}")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    logger.info("Auto-start disabled")
                except FileNotFoundError:
                    # Already disabled
                    pass
            return True
        finally:
            winreg.CloseKey(key)

    except PermissionError:
        logger.error("Permission denied when modifying registry")
        return False
    except Exception as e:
        logger.error(f"Failed to set autostart: {e}")
        return False
