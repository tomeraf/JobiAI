from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path
import os
import sys


def get_data_dir() -> Path:
    """Get the application data directory."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - use LOCALAPPDATA
        base = Path(os.environ.get('LOCALAPPDATA', Path.home()))
        return base / 'JobiAI'
    else:
        # Development mode - use backend directory
        return Path(__file__).parent.parent


def get_default_database_url() -> str:
    """Get the default database URL based on environment."""
    # If DATABASE_URL is set, use it (for dev mode with PostgreSQL)
    if os.environ.get('DATABASE_URL'):
        return os.environ['DATABASE_URL']

    # Default to SQLite in data directory
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{data_dir / 'jobiai.db'}"


class Settings(BaseSettings):
    # Data directory for app files
    data_dir: Path = get_data_dir()

    # Database - defaults to SQLite, can be overridden with DATABASE_URL env var
    database_url: str = get_default_database_url()

    @field_validator('database_url', mode='before')
    @classmethod
    def strip_database_url(cls, v):
        """Strip whitespace from DATABASE_URL (batch files can add trailing spaces)."""
        if isinstance(v, str):
            return v.strip()
        return v

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return 'sqlite' in self.database_url

    # LinkedIn data directory (for credentials storage)
    linkedin_data_dir: Path = Path(__file__).parent.parent / "linkedin_data"

    # Rate limits (daily)
    max_connections_per_day: int = 50
    max_messages_per_day: int = 100

    # Delays (seconds)
    min_action_delay: float = 2.0
    max_action_delay: float = 5.0

    class Config:
        # Only load .env if DATABASE_URL not already set (VBS launcher sets it)
        env_file = ".env" if not os.environ.get('DATABASE_URL') else None
        env_file_encoding = "utf-8"


settings = Settings()
