"""
Unit tests for application configuration.
"""
import pytest
import os
from pathlib import Path
from unittest.mock import patch

from app.config import Settings, settings


class TestSettings:
    """Tests for Settings class."""

    def test_settings_has_database_url(self):
        """Test that settings has database_url."""
        assert hasattr(settings, "database_url")
        assert isinstance(settings.database_url, str)
        assert "postgresql" in settings.database_url

    def test_settings_has_linkedin_data_dir(self):
        """Test that settings has linkedin_data_dir."""
        assert hasattr(settings, "linkedin_data_dir")
        assert isinstance(settings.linkedin_data_dir, Path)

    def test_settings_has_rate_limits(self):
        """Test that settings has rate limit configuration."""
        assert hasattr(settings, "max_connections_per_day")
        assert hasattr(settings, "max_messages_per_day")
        assert isinstance(settings.max_connections_per_day, int)
        assert isinstance(settings.max_messages_per_day, int)

    def test_settings_has_delays(self):
        """Test that settings has delay configuration."""
        assert hasattr(settings, "min_action_delay")
        assert hasattr(settings, "max_action_delay")
        assert isinstance(settings.min_action_delay, float)
        assert isinstance(settings.max_action_delay, float)

    def test_settings_default_values(self):
        """Test default values are sensible."""
        # Rate limits should be positive
        assert settings.max_connections_per_day > 0
        assert settings.max_messages_per_day > 0

        # Delays should be positive
        assert settings.min_action_delay > 0
        assert settings.max_action_delay > settings.min_action_delay


class TestSettingsDefaults:
    """Tests for Settings default values."""

    def test_default_max_connections(self):
        """Test default max connections per day."""
        s = Settings()
        assert s.max_connections_per_day == 50

    def test_default_max_messages(self):
        """Test default max messages per day."""
        s = Settings()
        assert s.max_messages_per_day == 100

    def test_default_min_delay(self):
        """Test default minimum action delay."""
        s = Settings()
        assert s.min_action_delay == 2.0

    def test_default_max_delay(self):
        """Test default maximum action delay."""
        s = Settings()
        assert s.max_action_delay == 5.0


class TestSettingsEnvironmentVariables:
    """Tests for environment variable configuration."""

    def test_database_url_from_env(self):
        """Test that DATABASE_URL can be set from environment."""
        custom_url = "postgresql+asyncpg://custom:custom@customhost:5432/customdb"

        with patch.dict(os.environ, {"DATABASE_URL": custom_url}):
            s = Settings()
            assert s.database_url == custom_url


class TestSettingsLinkedInDataDir:
    """Tests for LinkedIn data directory configuration."""

    def test_linkedin_data_dir_is_path(self):
        """Test that linkedin_data_dir is a Path object."""
        s = Settings()
        assert isinstance(s.linkedin_data_dir, Path)

    def test_linkedin_data_dir_has_linkedin_data_name(self):
        """Test that linkedin_data_dir path includes 'linkedin_data'."""
        s = Settings()
        assert "linkedin_data" in str(s.linkedin_data_dir)


class TestSettingsSingleton:
    """Tests for settings singleton behavior."""

    def test_settings_instance_exists(self):
        """Test that a settings instance is available."""
        from app.config import settings as imported_settings
        assert imported_settings is not None

    def test_settings_is_settings_instance(self):
        """Test that settings is a Settings instance."""
        assert isinstance(settings, Settings)


class TestSettingsValidation:
    """Tests for settings validation logic."""

    def test_delays_relationship(self):
        """Test that max delay is greater than min delay."""
        assert settings.max_action_delay > settings.min_action_delay

    def test_rate_limits_reasonable(self):
        """Test that rate limits are within reasonable bounds."""
        # LinkedIn typically allows ~100 connections/week, 150 messages/day
        assert settings.max_connections_per_day <= 100
        assert settings.max_messages_per_day <= 200
