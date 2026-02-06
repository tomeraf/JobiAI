"""
JobiAI Hidden Launcher

Starts the backend and frontend as hidden background processes.
Shows a system tray icon for control.

Requirements:
- Python 3.11+ with packages from backend/requirements.txt
- Node.js with npm (for frontend dev server)
- Playwright browsers installed: playwright install chromium

Usage:
- Double-click this file to start JobiAI in the background
- Right-click the tray icon to open UI or exit
"""

import subprocess
import sys
import os
import webbrowser
import time
import threading
import signal
from pathlib import Path

# Add backend to path
SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR / "backend"
FRONTEND_DIR = SCRIPT_DIR / "frontend"

sys.path.insert(0, str(BACKEND_DIR))

# Set SQLite database path
DATA_DIR = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'JobiAI'
DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ['DATABASE_URL'] = f"sqlite+aiosqlite:///{DATA_DIR / 'jobiai.db'}"

# Import after setting up environment
try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    print("Please install: pip install pystray pillow")
    sys.exit(1)


class HiddenLauncher:
    """Launches backend and frontend as hidden processes."""

    def __init__(self):
        self.backend_process = None
        self.frontend_process = None
        self.icon = None
        self.backend_port = 9000
        self.frontend_port = 5173
        self._running = False

    def find_available_port(self, start_port, max_attempts=100):
        """Find an available port starting from start_port."""
        import socket
        for port in range(start_port, start_port + max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', port))
                    return port
            except OSError:
                continue
        return start_port  # Fallback

    def create_icon(self, size=64):
        """Create a simple tray icon."""
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        # Blue circle
        draw.ellipse([2, 2, size-2, size-2], fill='#4A90D9')
        # White "J"
        draw.text((size//3, size//6), "J", fill='white')
        return image

    def start_backend(self):
        """Start the FastAPI backend as a hidden process."""
        self.backend_port = self.find_available_port(9000)

        # Create startup info to hide the window (Windows only)
        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        env = os.environ.copy()
        env['DATABASE_URL'] = f"sqlite+aiosqlite:///{DATA_DIR / 'jobiai.db'}"

        cmd = [
            sys.executable, '-m', 'uvicorn',
            'app.main:app',
            '--host', '127.0.0.1',
            '--port', str(self.backend_port),
            '--log-level', 'warning'
        ]

        self.backend_process = subprocess.Popen(
            cmd,
            cwd=str(BACKEND_DIR),
            startupinfo=startupinfo,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        print(f"Backend started on port {self.backend_port} (PID: {self.backend_process.pid})")

    def start_frontend(self):
        """Start the Vite frontend dev server as a hidden process."""
        self.frontend_port = self.find_available_port(5173)

        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        env = os.environ.copy()
        env['VITE_API_URL'] = f"http://localhost:{self.backend_port}"

        # Use npm.cmd on Windows
        npm_cmd = 'npm.cmd' if sys.platform == 'win32' else 'npm'

        cmd = [npm_cmd, 'run', 'dev', '--', '--port', str(self.frontend_port)]

        self.frontend_process = subprocess.Popen(
            cmd,
            cwd=str(FRONTEND_DIR),
            startupinfo=startupinfo,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            shell=True  # Needed for npm on Windows
        )
        print(f"Frontend started on port {self.frontend_port} (PID: {self.frontend_process.pid})")

    def open_ui(self, icon=None, item=None):
        """Open the web UI in the default browser."""
        url = f"http://localhost:{self.frontend_port}"
        webbrowser.open(url)

    def stop_all(self, icon=None, item=None):
        """Stop all processes and exit."""
        print("Stopping JobiAI...")
        self._running = False

        if self.backend_process:
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.backend_process.kill()

        if self.frontend_process:
            self.frontend_process.terminate()
            try:
                self.frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.frontend_process.kill()

        if self.icon:
            self.icon.stop()

    def run(self):
        """Start everything and show tray icon."""
        print("Starting JobiAI...")
        self._running = True

        # Start services
        self.start_backend()
        time.sleep(2)  # Wait for backend to initialize
        self.start_frontend()
        time.sleep(2)  # Wait for frontend to initialize

        # Open browser on first run
        self.open_ui()

        # Create tray icon
        menu = pystray.Menu(
            pystray.MenuItem('Open JobiAI', self.open_ui, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Exit', self.stop_all),
        )

        self.icon = pystray.Icon(
            'JobiAI',
            self.create_icon(),
            'JobiAI - LinkedIn Job Bot',
            menu=menu
        )

        print("JobiAI is running. Right-click the tray icon to access menu.")
        self.icon.run()  # This blocks


def check_single_instance():
    """Ensure only one instance is running."""
    try:
        import win32event
        import win32api
        import winerror

        mutex = win32event.CreateMutex(None, False, "JobiAI_HiddenLauncher_Mutex")
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            print("JobiAI is already running!")
            return False
        return True
    except ImportError:
        return True  # pywin32 not available


if __name__ == '__main__':
    if not check_single_instance():
        sys.exit(0)

    launcher = HiddenLauncher()
    try:
        launcher.run()
    except KeyboardInterrupt:
        launcher.stop_all()
