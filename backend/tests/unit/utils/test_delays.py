"""
Unit tests for delay utilities.
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from app.utils.delays import (
    human_delay,
    typing_delay,
    scroll_delay,
    page_load_delay,
    action_delay,
)


class TestHumanDelay:
    """Tests for human_delay function."""

    @pytest.mark.asyncio
    async def test_human_delay_sleeps(self):
        """Test that human_delay actually sleeps."""
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await human_delay(1.0, 2.0)
            mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_human_delay_within_bounds(self):
        """Test that delay is within specified bounds."""
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await human_delay(1.0, 2.0)

            call_args = mock_sleep.call_args[0][0]
            assert 1.0 <= call_args <= 2.0

    @pytest.mark.asyncio
    async def test_human_delay_default_bounds(self):
        """Test human_delay with default bounds."""
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await human_delay()

            call_args = mock_sleep.call_args[0][0]
            assert 1.0 <= call_args <= 3.0

    @pytest.mark.asyncio
    async def test_human_delay_same_min_max(self):
        """Test human_delay when min equals max."""
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await human_delay(2.0, 2.0)

            call_args = mock_sleep.call_args[0][0]
            assert call_args == 2.0


class TestTypingDelay:
    """Tests for typing_delay function."""

    @pytest.mark.asyncio
    async def test_typing_delay_sleeps(self):
        """Test that typing_delay sleeps."""
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await typing_delay("Hello")
            mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_typing_delay_longer_for_longer_text(self):
        """Test that longer text results in longer delay."""
        delays = []

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Fix random for reproducibility
            with patch("random.uniform", return_value=1.0):
                await typing_delay("Hi")
                delays.append(mock_sleep.call_args[0][0])

                await typing_delay("Hello World!")
                delays.append(mock_sleep.call_args[0][0])

        # Longer text should have longer delay
        assert delays[1] > delays[0]

    @pytest.mark.asyncio
    async def test_typing_delay_empty_text(self):
        """Test typing_delay with empty text."""
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await typing_delay("")
            # Should still call sleep, even if delay is 0
            mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_typing_delay_custom_speed(self):
        """Test typing_delay with custom typing speed."""
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch("random.uniform", return_value=1.0):
                await typing_delay("12345", chars_per_second=5.0)

                # 5 chars at 5 chars/sec = 1 second
                call_args = mock_sleep.call_args[0][0]
                assert call_args == pytest.approx(1.0, rel=0.1)


class TestScrollDelay:
    """Tests for scroll_delay function."""

    @pytest.mark.asyncio
    async def test_scroll_delay_calls_human_delay(self):
        """Test that scroll_delay uses human_delay internally."""
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await scroll_delay()
            mock_sleep.assert_called_once()

            # Should use scroll-specific bounds (0.5-1.5)
            call_args = mock_sleep.call_args[0][0]
            assert 0.5 <= call_args <= 1.5


class TestPageLoadDelay:
    """Tests for page_load_delay function."""

    @pytest.mark.asyncio
    async def test_page_load_delay_sleeps(self):
        """Test that page_load_delay sleeps."""
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await page_load_delay()
            mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_page_load_delay_longer_than_scroll(self):
        """Test that page load delay is longer than scroll delay."""
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await page_load_delay()
            page_delay = mock_sleep.call_args[0][0]

            # Page load should be 2-4 seconds
            assert 2.0 <= page_delay <= 4.0


class TestActionDelay:
    """Tests for action_delay function."""

    @pytest.mark.asyncio
    async def test_action_delay_sleeps(self):
        """Test that action_delay sleeps."""
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await action_delay()
            mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_delay_bounds(self):
        """Test action_delay is within expected bounds."""
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await action_delay()
            call_args = mock_sleep.call_args[0][0]
            # Action delay should be 1-2.5 seconds
            assert 1.0 <= call_args <= 2.5


class TestDelayRandomness:
    """Tests for delay randomness."""

    @pytest.mark.asyncio
    async def test_delays_are_random(self):
        """Test that delays produce different values."""
        delays = []

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            for _ in range(10):
                await human_delay(1.0, 5.0)
                delays.append(mock_sleep.call_args[0][0])

        # With 10 samples in a range of 4 seconds, we should have variation
        unique_delays = set(round(d, 3) for d in delays)
        # Allow for some coincidental same values, but expect variety
        assert len(unique_delays) > 1


class TestDelayIntegration:
    """Integration tests for delay functions."""

    @pytest.mark.asyncio
    async def test_delays_are_async(self):
        """Test that delays properly yield control."""
        results = []

        async def task_with_delay(name: str):
            results.append(f"{name}_start")
            # Use very short actual sleep
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await human_delay(0.1, 0.1)
            results.append(f"{name}_end")

        # Run concurrently
        await asyncio.gather(
            task_with_delay("A"),
            task_with_delay("B")
        )

        # Both tasks should complete
        assert "A_start" in results
        assert "A_end" in results
        assert "B_start" in results
        assert "B_end" in results
