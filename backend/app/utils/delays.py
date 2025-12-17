import asyncio
import random


async def human_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """Add a random delay to simulate human behavior."""
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def typing_delay(text: str, chars_per_second: float = 5.0) -> None:
    """Simulate human typing speed."""
    typing_time = len(text) / chars_per_second
    # Add some randomness
    typing_time *= random.uniform(0.8, 1.2)
    await asyncio.sleep(typing_time)


async def scroll_delay() -> None:
    """Delay after scrolling action."""
    await human_delay(0.5, 1.5)


async def page_load_delay() -> None:
    """Delay after page navigation."""
    await human_delay(2.0, 4.0)


async def action_delay() -> None:
    """Delay between significant actions (clicking buttons, etc)."""
    await human_delay(1.0, 2.5)
