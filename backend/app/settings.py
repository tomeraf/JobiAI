"""
Application Settings Manager

Handles user preferences stored in a JSON file.
Separate from config.py which handles environment-based configuration.
"""

import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AppSettings:
    """User-configurable application settings."""

    # Server
    port: int = 9000

    # Browser behavior
    browser_visible: bool = False  # Hidden by default

    # Windows integration
    auto_start: bool = False  # Start with Windows
    minimize_to_tray: bool = True  # Minimize to tray instead of taskbar

    # First run flag
    first_run: bool = True

    # Window state (for restoring position)
    window_x: Optional[int] = None
    window_y: Optional[int] = None

    @classmethod
    def load(cls, path: Path) -> 'AppSettings':
        """Load settings from JSON file."""
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"Loaded settings from {path}")
                # Filter out unknown keys
                valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
                filtered_data = {k: v for k, v in data.items() if k in valid_keys}
                return cls(**filtered_data)
            except Exception as e:
                logger.warning(f"Failed to load settings: {e}, using defaults")
                return cls()
        else:
            logger.info(f"Settings file not found at {path}, using defaults")
            return cls()

    def save(self, path: Path) -> None:
        """Save settings to JSON file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self), f, indent=2)
            logger.info(f"Saved settings to {path}")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def update(self, **kwargs) -> None:
        """Update settings with provided values."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


# Global settings instance (initialized by TrayApp)
_settings: Optional[AppSettings] = None
_settings_path: Optional[Path] = None


def get_settings() -> AppSettings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        raise RuntimeError("Settings not initialized. Call init_settings() first.")
    return _settings


def init_settings(data_dir: Path) -> AppSettings:
    """Initialize global settings from data directory."""
    global _settings, _settings_path
    _settings_path = data_dir / 'settings.json'
    _settings = AppSettings.load(_settings_path)
    return _settings


def save_settings() -> None:
    """Save current settings to disk."""
    global _settings, _settings_path
    if _settings and _settings_path:
        _settings.save(_settings_path)
