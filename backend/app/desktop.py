"""
JobiAI Desktop Application Entry Point

This is the main entry point for the desktop (system tray) version of JobiAI.
It initializes the tray app with proper data directories and runs the application.

Usage:
    python -m app.desktop
    or
    JobiAI.exe (when packaged with PyInstaller)
"""

import sys
import os
from pathlib import Path


def setup_environment():
    """Set up environment for desktop mode."""
    # Determine if running as frozen executable
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        app_dir = Path(sys._MEIPASS)
        # Use LOCALAPPDATA for user data
        data_dir = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'JobiAI'
    else:
        # Development mode
        app_dir = Path(__file__).parent.parent
        data_dir = app_dir

    # Ensure data directory exists
    data_dir.mkdir(parents=True, exist_ok=True)

    return app_dir, data_dir


def check_single_instance():
    """
    Ensure only one instance of the app is running.
    Returns True if this is the only instance.
    """
    try:
        import win32event
        import win32api
        import winerror

        # Create a named mutex
        mutex_name = "JobiAI_SingleInstance_Mutex"
        mutex = win32event.CreateMutex(None, False, mutex_name)
        last_error = win32api.GetLastError()

        if last_error == winerror.ERROR_ALREADY_EXISTS:
            # Another instance is already running
            print("JobiAI is already running. Check your system tray.")

            # Try to bring existing window to front
            try:
                import win32gui
                import win32con

                def bring_to_front(hwnd, _):
                    title = win32gui.GetWindowText(hwnd)
                    if "JobiAI" in title:
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd)
                        return False
                    return True

                win32gui.EnumWindows(bring_to_front, None)
            except:
                pass

            return False

        return True

    except ImportError:
        # pywin32 not available, allow running
        return True


def main():
    """Main entry point for the desktop application."""
    # Check for single instance
    if not check_single_instance():
        sys.exit(0)

    # Set up environment
    app_dir, data_dir = setup_environment()

    # Set up browser path environment variable for Playwright
    # This must be done before importing any Playwright-related modules
    from app.tray.browser_installer import set_browser_path_env
    set_browser_path_env()

    # Import and run tray app
    from app.tray import TrayApp

    app = TrayApp(data_dir=data_dir, app_dir=app_dir)
    app.run()


if __name__ == '__main__':
    main()
