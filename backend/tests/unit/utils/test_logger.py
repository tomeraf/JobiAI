"""
Unit tests for logger utility.
"""
import pytest
import logging
from unittest.mock import patch

from app.utils.logger import get_logger


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a Logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_uses_name(self):
        """Test that logger uses provided name."""
        logger = get_logger("my_custom_name")
        assert logger.name == "my_custom_name"

    def test_get_logger_returns_same_instance(self):
        """Test that same name returns same logger instance."""
        logger1 = get_logger("same_name")
        logger2 = get_logger("same_name")
        assert logger1 is logger2

    def test_get_logger_different_names(self):
        """Test that different names return different loggers."""
        logger1 = get_logger("name_one")
        logger2 = get_logger("name_two")
        assert logger1 is not logger2

    def test_get_logger_can_log(self):
        """Test that returned logger can log messages."""
        logger = get_logger("test_logging")

        # Should not raise
        logger.info("Test info message")
        logger.debug("Test debug message")
        logger.warning("Test warning message")
        logger.error("Test error message")

    def test_get_logger_with_module_name(self):
        """Test using __name__ pattern."""
        logger = get_logger(__name__)
        # Should use the test module name
        assert "test_logger" in logger.name or __name__ == logger.name


class TestLoggerConfiguration:
    """Tests for logger configuration."""

    def test_logger_has_handler(self):
        """Test that logger has at least one handler or inherits from root."""
        logger = get_logger("handler_test")
        # Either has handlers or will use root logger handlers
        has_handlers = len(logger.handlers) > 0 or logger.parent is not None
        assert has_handlers

    def test_logger_level_allows_info(self):
        """Test that logger level allows INFO messages."""
        logger = get_logger("level_test")
        # Logger or its effective level should allow INFO
        effective_level = logger.getEffectiveLevel()
        assert effective_level <= logging.INFO


class TestLoggerUsage:
    """Tests for typical logger usage patterns."""

    def test_logger_in_class(self):
        """Test using logger in a class."""
        class MyClass:
            def __init__(self):
                self.logger = get_logger(self.__class__.__name__)

            def do_something(self):
                self.logger.info("Doing something")
                return True

        obj = MyClass()
        assert obj.do_something() is True
        assert obj.logger.name == "MyClass"

    def test_logger_with_extra_info(self):
        """Test logging with extra context."""
        logger = get_logger("extra_test")

        # Should not raise when using standard logging features
        logger.info("Processing item %s", "test_item")
        logger.info("Count: %d", 42)
        logger.info("Values: %s, %s", "a", "b")

    def test_logger_exception_logging(self):
        """Test logging exceptions."""
        logger = get_logger("exception_test")

        try:
            raise ValueError("Test error")
        except ValueError:
            # Should not raise
            logger.exception("An error occurred")

    def test_multiple_loggers_independent(self):
        """Test that multiple loggers are independent."""
        logger_a = get_logger("module_a")
        logger_b = get_logger("module_b")

        # Setting level on one shouldn't affect the other
        original_level_b = logger_b.level

        logger_a.setLevel(logging.CRITICAL)

        # Logger B should be unaffected
        assert logger_b.level == original_level_b or logger_b.level != logging.CRITICAL
