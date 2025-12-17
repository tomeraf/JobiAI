from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jobiai"

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
