"""
Unit tests for LinkedInMessaging service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.linkedin.messaging import LinkedInMessaging


class TestLinkedInMessagingInitialization:
    """Tests for messaging initialization."""

    def test_messaging_creates_own_browser(self):
        """Test that messaging creates own browser."""
        messaging = LinkedInMessaging()
        assert messaging.browser is not None
        assert messaging._owns_browser is True

    def test_messaging_uses_provided_browser(self):
        """Test that messaging uses provided browser."""
        mock_browser = MagicMock()
        messaging = LinkedInMessaging(browser=mock_browser)
        assert messaging.browser is mock_browser
        assert messaging._owns_browser is False


class TestLinkedInMessagingSendMessage:
    """Tests for sending messages."""

    @pytest.fixture
    def mock_messaging(self):
        """Create mock messaging service."""
        mock_browser = MagicMock()
        mock_page = AsyncMock()
        mock_browser.page = mock_page
        mock_browser.goto = AsyncMock()

        messaging = LinkedInMessaging(browser=mock_browser)
        return messaging, mock_page

    @pytest.mark.asyncio
    async def test_send_message_navigates_to_profile(self, mock_messaging):
        """Test that send_message navigates to profile."""
        messaging, mock_page = mock_messaging
        mock_page.wait_for_selector = AsyncMock(return_value=None)

        with patch("app.services.linkedin.messaging.human_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.messaging.action_delay", new_callable=AsyncMock):
            await messaging.send_message(
                "https://linkedin.com/in/testuser",
                "Hello, this is a test message!"
            )

        messaging.browser.goto.assert_called_with("https://linkedin.com/in/testuser")

    @pytest.mark.asyncio
    async def test_send_message_returns_false_if_no_button(self, mock_messaging):
        """Test that send_message returns False if no message button."""
        messaging, mock_page = mock_messaging
        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))

        with patch("app.services.linkedin.messaging.human_delay", new_callable=AsyncMock):
            result = await messaging.send_message(
                "https://linkedin.com/in/testuser",
                "Hello!"
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_clicks_message_button(self, mock_messaging):
        """Test that send_message clicks the message button."""
        messaging, mock_page = mock_messaging

        mock_button = AsyncMock()
        mock_button.is_visible = AsyncMock(return_value=True)
        mock_button.click = AsyncMock()

        # First wait_for_selector returns message button
        mock_page.wait_for_selector = AsyncMock(return_value=mock_button)

        with patch("app.services.linkedin.messaging.human_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.messaging.action_delay", new_callable=AsyncMock):
            # Mock the message window handling to return False (we're testing button click)
            messaging._handle_message_window = AsyncMock(return_value=False)

            await messaging.send_message(
                "https://linkedin.com/in/testuser",
                "Hello!"
            )

        mock_button.click.assert_called()

    @pytest.mark.asyncio
    async def test_send_message_success(self, mock_messaging):
        """Test successful message sending."""
        messaging, mock_page = mock_messaging

        mock_button = AsyncMock()
        mock_button.is_visible = AsyncMock(return_value=True)
        mock_button.click = AsyncMock()

        mock_page.wait_for_selector = AsyncMock(return_value=mock_button)

        with patch("app.services.linkedin.messaging.human_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.messaging.action_delay", new_callable=AsyncMock):
            messaging._handle_message_window = AsyncMock(return_value=True)

            result = await messaging.send_message(
                "https://linkedin.com/in/testuser",
                "Hello!"
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_message_handles_exception(self, mock_messaging):
        """Test that exceptions are handled."""
        messaging, mock_page = mock_messaging
        messaging.browser.goto = AsyncMock(side_effect=Exception("Network error"))

        with patch("app.services.linkedin.messaging.human_delay", new_callable=AsyncMock):
            result = await messaging.send_message(
                "https://linkedin.com/in/testuser",
                "Hello!"
            )

        assert result is False


class TestLinkedInMessagingGenderedMessage:
    """Tests for gender-aware messaging."""

    @pytest.fixture
    def mock_messaging(self):
        """Create mock messaging service."""
        mock_browser = MagicMock()
        mock_page = AsyncMock()
        mock_browser.page = mock_page
        mock_browser.goto = AsyncMock()

        messaging = LinkedInMessaging(browser=mock_browser)
        messaging.send_message = AsyncMock(return_value=True)
        return messaging

    @pytest.mark.asyncio
    async def test_gendered_message_detects_male(self, mock_messaging):
        """Test gendered message with male name."""
        messaging = mock_messaging

        with patch("app.services.linkedin.messaging.detect_gender", return_value="male"):
            result, gender = await messaging.send_gendered_message(
                profile_url="https://linkedin.com/in/david",
                name="David Cohen",
                company="Google",
                template_male="Hi {name}, I saw you work at {company}!",
                template_female="Hi {name}, I saw you work at {company}!",
                template_neutral="Hello {name}, nice to connect!"
            )

        assert gender == "male"
        # Check the message was formatted with male template
        call_args = messaging.send_message.call_args[0]
        assert "David" in call_args[1]
        assert "Google" in call_args[1]

    @pytest.mark.asyncio
    async def test_gendered_message_detects_female(self, mock_messaging):
        """Test gendered message with female name."""
        messaging = mock_messaging

        with patch("app.services.linkedin.messaging.detect_gender", return_value="female"):
            result, gender = await messaging.send_gendered_message(
                profile_url="https://linkedin.com/in/sarah",
                name="Sarah Levi",
                company="Microsoft",
                template_male="Male template",
                template_female="Female: Hi {name} at {company}!",
                template_neutral="Neutral template"
            )

        assert gender == "female"
        call_args = messaging.send_message.call_args[0]
        assert "Female:" in call_args[1]

    @pytest.mark.asyncio
    async def test_gendered_message_uses_neutral_for_unknown(self, mock_messaging):
        """Test gendered message uses neutral for unknown gender."""
        messaging = mock_messaging

        with patch("app.services.linkedin.messaging.detect_gender", return_value="unknown"):
            result, gender = await messaging.send_gendered_message(
                profile_url="https://linkedin.com/in/unknown",
                name="Unknown Person",
                company="Company",
                template_male="Male template",
                template_female="Female template",
                template_neutral="Neutral: {name} at {company}"
            )

        assert gender == "unknown"
        call_args = messaging.send_message.call_args[0]
        assert "Neutral:" in call_args[1]

    @pytest.mark.asyncio
    async def test_gendered_message_uses_known_gender(self, mock_messaging):
        """Test that known gender overrides detection."""
        messaging = mock_messaging

        with patch("app.services.linkedin.messaging.detect_gender") as mock_detect:
            result, gender = await messaging.send_gendered_message(
                profile_url="https://linkedin.com/in/test",
                name="Test Person",
                company="Company",
                template_male="Male: {name}",
                template_female="Female: {name}",
                template_neutral="Neutral: {name}",
                known_gender="female"
            )

        # Should not call detect_gender when known_gender is provided
        assert gender == "female"

    @pytest.mark.asyncio
    async def test_gendered_message_extracts_first_name(self, mock_messaging):
        """Test that first name is extracted from full name."""
        messaging = mock_messaging

        with patch("app.services.linkedin.messaging.detect_gender", return_value="male"):
            await messaging.send_gendered_message(
                profile_url="https://linkedin.com/in/test",
                name="John Michael Smith",
                company="Company",
                template_male="Hi {name}!",
                template_female="Hi {name}!",
                template_neutral="Hi {name}!"
            )

        call_args = messaging.send_message.call_args[0]
        # Should use first name only
        assert "John" in call_args[1]
        assert "Michael" not in call_args[1]


class TestLinkedInMessagingBulkMessages:
    """Tests for bulk messaging."""

    @pytest.fixture
    def mock_messaging(self):
        """Create mock messaging service."""
        mock_browser = MagicMock()
        messaging = LinkedInMessaging(browser=mock_browser)
        messaging.send_gendered_message = AsyncMock(return_value=(True, "male"))
        return messaging

    @pytest.mark.asyncio
    async def test_bulk_messages_processes_all_contacts(self, mock_messaging):
        """Test that bulk messaging processes all contacts."""
        messaging = mock_messaging

        contacts = [
            {"linkedin_url": "https://linkedin.com/in/user1", "name": "User 1"},
            {"linkedin_url": "https://linkedin.com/in/user2", "name": "User 2"},
            {"linkedin_url": "https://linkedin.com/in/user3", "name": "User 3"},
        ]

        with patch("app.services.linkedin.messaging.human_delay", new_callable=AsyncMock):
            result = await messaging.send_bulk_messages(
                contacts=contacts,
                template_male="Male",
                template_female="Female",
                template_neutral="Neutral",
                company="Test"
            )

        assert len(result["sent"]) == 3
        assert len(result["failed"]) == 0
        assert len(result["skipped"]) == 0

    @pytest.mark.asyncio
    async def test_bulk_messages_skips_already_messaged(self, mock_messaging):
        """Test that already messaged contacts are skipped."""
        messaging = mock_messaging

        from datetime import datetime
        contacts = [
            {"linkedin_url": "https://linkedin.com/in/user1", "name": "User 1"},
            {"linkedin_url": "https://linkedin.com/in/user2", "name": "User 2", "message_sent_at": datetime.now()},
        ]

        with patch("app.services.linkedin.messaging.human_delay", new_callable=AsyncMock):
            result = await messaging.send_bulk_messages(
                contacts=contacts,
                template_male="M",
                template_female="F",
                template_neutral="N",
                company="Test"
            )

        assert len(result["sent"]) == 1
        assert len(result["skipped"]) == 1

    @pytest.mark.asyncio
    async def test_bulk_messages_skips_missing_url(self, mock_messaging):
        """Test that contacts without URL are skipped."""
        messaging = mock_messaging

        contacts = [
            {"linkedin_url": "https://linkedin.com/in/user1", "name": "User 1"},
            {"name": "User 2"},  # No URL
        ]

        with patch("app.services.linkedin.messaging.human_delay", new_callable=AsyncMock):
            result = await messaging.send_bulk_messages(
                contacts=contacts,
                template_male="M",
                template_female="F",
                template_neutral="N",
                company="Test"
            )

        assert len(result["sent"]) == 1
        assert len(result["skipped"]) == 1

    @pytest.mark.asyncio
    async def test_bulk_messages_tracks_failures(self, mock_messaging):
        """Test that failed messages are tracked."""
        messaging = mock_messaging
        messaging.send_gendered_message = AsyncMock(side_effect=[
            (True, "male"),
            (False, "female"),
            (True, "male"),
        ])

        contacts = [
            {"linkedin_url": "https://linkedin.com/in/user1", "name": "User 1"},
            {"linkedin_url": "https://linkedin.com/in/user2", "name": "User 2"},
            {"linkedin_url": "https://linkedin.com/in/user3", "name": "User 3"},
        ]

        with patch("app.services.linkedin.messaging.human_delay", new_callable=AsyncMock):
            result = await messaging.send_bulk_messages(
                contacts=contacts,
                template_male="M",
                template_female="F",
                template_neutral="N",
                company="Test"
            )

        assert len(result["sent"]) == 2
        assert len(result["failed"]) == 1


class TestLinkedInMessagingCleanup:
    """Tests for messaging cleanup."""

    @pytest.mark.asyncio
    async def test_close_own_browser(self):
        """Test closing own browser."""
        messaging = LinkedInMessaging()
        messaging.browser.close = AsyncMock()

        await messaging.close()

        messaging.browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_provided_browser_not_closed(self):
        """Test that provided browser is not closed."""
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()
        messaging = LinkedInMessaging(browser=mock_browser)

        await messaging.close()

        mock_browser.close.assert_not_called()
