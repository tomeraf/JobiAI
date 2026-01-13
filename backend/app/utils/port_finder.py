"""
Port detection and allocation utility for dynamic port management.
"""
import socket
import json
import subprocess
import re
import sys
from pathlib import Path
from typing import Optional, Union, List, Set
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Configuration file shared between backend and frontend
CONFIG_FILE = Path(__file__).parent.parent.parent.parent / ".ports.json"

# Default ports to try
DEFAULT_BACKEND_PORT = 9000
DEFAULT_FRONTEND_PORT = 5173
DEFAULT_DATABASE_PORT = 5436

# Port ranges - use higher ports that are less likely to be Windows-reserved
BACKEND_PORT_RANGE = range(9000, 9100)
FRONTEND_PORT_RANGE = range(5173, 6000)
# Database: try common postgres ports first, then higher ranges
DATABASE_PORT_RANGE = [5432, 5433, 5434, 5435, 5436] + list(range(15432, 15532)) + list(range(25432, 25532))


def get_windows_excluded_ports() -> Set[int]:
    """
    Get the set of ports excluded by Windows (Hyper-V, WSL, etc).

    Returns:
        Set of excluded port numbers
    """
    excluded = set()

    if sys.platform != 'win32':
        return excluded

    try:
        result = subprocess.run(
            ['netsh', 'interface', 'ipv4', 'show', 'excludedportrange', 'protocol=tcp'],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Parse output like:
        # Start Port    End Port
        # ----------    --------
        #       5435        5534
        for line in result.stdout.split('\n'):
            match = re.match(r'\s*(\d+)\s+(\d+)', line)
            if match:
                start, end = int(match.group(1)), int(match.group(2))
                for port in range(start, end + 1):
                    excluded.add(port)

        if excluded:
            logger.info(f"Found {len(excluded)} Windows-excluded ports")

    except Exception as e:
        logger.warning(f"Could not get Windows excluded ports: {e}")

    return excluded


# Cache the excluded ports (they don't change during runtime)
_windows_excluded_ports: Optional[Set[int]] = None


def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """
    Check if a port is available for binding.
    Also checks Windows excluded port ranges.

    Args:
        port: Port number to check
        host: Host address to check on

    Returns:
        True if port is available, False otherwise
    """
    global _windows_excluded_ports

    # Check Windows excluded ports first (cached)
    if _windows_excluded_ports is None:
        _windows_excluded_ports = get_windows_excluded_ports()

    if port in _windows_excluded_ports:
        return False

    # Try to bind to the port
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            return True
    except OSError:
        return False


def find_available_port(start_port: int, port_range: Union[range, List[int]]) -> Optional[int]:
    """
    Find an available port in the given range.

    Args:
        start_port: Preferred port to try first
        port_range: Range or list of ports to search

    Returns:
        Available port number or None if none found
    """
    # Try the preferred port first
    if start_port in port_range and is_port_available(start_port):
        return start_port

    # Try other ports in the range
    for port in port_range:
        if port == start_port:
            continue
        if is_port_available(port):
            return port

    return None


def get_backend_port() -> int:
    """
    Get an available port for the backend server.
    Tries ports from 9000-9099.

    Returns:
        Available port number

    Raises:
        RuntimeError: If no available port found
    """
    port = find_available_port(DEFAULT_BACKEND_PORT, BACKEND_PORT_RANGE)
    if port is None:
        raise RuntimeError(
            f"No available port found in range {BACKEND_PORT_RANGE.start}-{BACKEND_PORT_RANGE.stop-1}"
        )

    logger.info(f"Backend port detected: {port}")
    return port


def get_frontend_port() -> int:
    """
    Get an available port for the frontend server.
    Tries ports from 5173-5999.

    Returns:
        Available port number

    Raises:
        RuntimeError: If no available port found
    """
    port = find_available_port(DEFAULT_FRONTEND_PORT, FRONTEND_PORT_RANGE)
    if port is None:
        raise RuntimeError(
            f"No available port found in range {FRONTEND_PORT_RANGE.start}-{FRONTEND_PORT_RANGE.stop-1}"
        )

    logger.info(f"Frontend port detected: {port}")
    return port


def get_database_port() -> int:
    """
    Get an available port for the PostgreSQL database.
    Tries common postgres ports, then higher ranges.

    Returns:
        Available port number

    Raises:
        RuntimeError: If no available port found
    """
    port = find_available_port(DEFAULT_DATABASE_PORT, DATABASE_PORT_RANGE)
    if port is None:
        raise RuntimeError(
            f"No available port found for database (tried common ports and ranges 15432-15532, 25432-25532)"
        )

    logger.info(f"Database port detected: {port}")
    return port


def save_port_config(backend_port: int, frontend_port: int, database_port: int) -> None:
    """
    Save port configuration to shared file.

    Args:
        backend_port: Backend server port
        frontend_port: Frontend server port
        database_port: PostgreSQL database port
    """
    config = {
        "backend_port": backend_port,
        "frontend_port": frontend_port,
        "database_port": database_port,
        "backend_url": f"http://localhost:{backend_port}",
        "frontend_url": f"http://localhost:{frontend_port}",
        "database_url": f"postgresql://postgres:postgres@localhost:{database_port}/jobiai",
    }

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

    logger.info(f"Port configuration saved to {CONFIG_FILE}")


def load_port_config() -> dict:
    """
    Load port configuration from shared file.

    Returns:
        Configuration dictionary with port information
    """
    if not CONFIG_FILE.exists():
        # Return defaults if config doesn't exist
        return {
            "backend_port": DEFAULT_BACKEND_PORT,
            "frontend_port": DEFAULT_FRONTEND_PORT,
            "database_port": DEFAULT_DATABASE_PORT,
            "backend_url": f"http://localhost:{DEFAULT_BACKEND_PORT}",
            "frontend_url": f"http://localhost:{DEFAULT_FRONTEND_PORT}",
            "database_url": f"postgresql://postgres:postgres@localhost:{DEFAULT_DATABASE_PORT}/jobiai",
        }

    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load port config: {e}")
        # Return defaults on error
        return {
            "backend_port": DEFAULT_BACKEND_PORT,
            "frontend_port": DEFAULT_FRONTEND_PORT,
            "database_port": DEFAULT_DATABASE_PORT,
            "backend_url": f"http://localhost:{DEFAULT_BACKEND_PORT}",
            "frontend_url": f"http://localhost:{DEFAULT_FRONTEND_PORT}",
            "database_url": f"postgresql://postgres:postgres@localhost:{DEFAULT_DATABASE_PORT}/jobiai",
        }


def get_dynamic_cors_origins() -> list[str]:
    """
    Get CORS origins based on current port configuration.

    Returns:
        List of allowed CORS origins
    """
    config = load_port_config()
    return [
        config["frontend_url"],
        "http://localhost:5173",  # Keep default for backward compatibility
        "http://localhost:3000",  # Keep alternative for backward compatibility
    ]


if __name__ == "__main__":
    # CLI tool for port detection
    print("JobiAI Port Detection Tool")
    print("=" * 50)

    backend_port = get_backend_port()
    frontend_port = get_frontend_port()
    database_port = get_database_port()

    print(f"\nAvailable ports:")
    print(f"  Backend:  {backend_port}")
    print(f"  Frontend: {frontend_port}")
    print(f"  Database: {database_port}")

    save_port_config(backend_port, frontend_port, database_port)
    print(f"\nConfiguration saved to: {CONFIG_FILE}")
