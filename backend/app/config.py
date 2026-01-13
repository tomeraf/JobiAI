from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jobiai"

    @field_validator('database_url', mode='before')
    @classmethod
    def strip_database_url(cls, v):
        """Strip whitespace from DATABASE_URL (batch files can add trailing spaces)."""
        if isinstance(v, str):
            return v.strip()
        return v

    # LinkedIn data directory (for credentials storage)
    linkedin_data_dir: Path = Path(__file__).parent.parent / "linkedin_data"

    # Rate limits (daily)
    max_connections_per_day: int = 50
    max_messages_per_day: int = 100

    # Delays (seconds)
    min_action_delay: float = 2.0
    max_action_delay: float = 5.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
