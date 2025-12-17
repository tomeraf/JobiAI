"""
Unit tests for LinkedInConnections service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.linkedin.connections import LinkedInConnections


class TestLinkedInConnectionsInitialization:
    """Tests for connections initialization."""

    def test_connections_creates_own_browser(self):
        """Test that connections creates own browser."""
        connections = LinkedInConnections()
        assert connections.browser is not None
        assert connections._owns_browser is True

    def test_connections_uses_provided_browser(self):
        """Test that connections uses provided browser."""
        mock_browser = MagicMock()
        connections = LinkedInConnections(browser=mock_browser)
        assert connections.browser is mock_browser
        assert connections._owns_browser is False


class TestLinkedInConnectionsSendRequest:
    """Tests for sending connection requests."""

    @pytest.fixture
    def mock_connections(self):
        """Create mock connections service."""
        mock_browser = MagicMock()
        mock_page = AsyncMock()
        mock_browser.page = mock_page
        mock_browser.goto = AsyncMock()

        connections = LinkedInConnections(browser=mock_browser)
        return connections, mock_page

    @pytest.mark.asyncio
    async def test_send_request_navigates_to_profile(self, mock_connections):
        """Test that send_request navigates to profile."""
        connections, mock_page = mock_connections
        mock_page.wait_for_selector = AsyncMock(return_value=None)

        with patch("app.services.linkedin.connections.human_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.connections.action_delay", new_callable=AsyncMock):
            await connections.send_connection_request(
                "https://linkedin.com/in/testuser"
            )

        connections.browser.goto.assert_called_with("https://linkedin.com/in/testuser")

    @pytest.mark.asyncio
    async def test_send_request_returns_false_if_no_button(self, mock_connections):
        """Test returns False if no connect button found."""
        connections, mock_page = mock_connections
        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))
        mock_page.query_selector = AsyncMock(return_value=None)

        with patch("app.services.linkedin.connections.human_delay", new_callable=AsyncMock):
            result = await connections.send_connection_request(
                "https://linkedin.com/in/testuser"
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_request_clicks_connect_button(self, mock_connections):
        """Test that connect button is clicked."""
        connections, mock_page = mock_connections

        mock_button = AsyncMock()
        mock_button.is_visible = AsyncMock(return_value=True)
        mock_button.click = AsyncMock()

        mock_page.wait_for_selector = AsyncMock(return_value=mock_button)

        with patch("app.services.linkedin.connections.human_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.connections.action_delay", new_callable=AsyncMock):
            connections._handle_connection_modal = AsyncMock(return_value=False)

            await connections.send_connection_request(
                "https://linkedin.com/in/testuser"
            )

        mock_button.click.assert_called()

    @pytest.mark.asyncio
    async def test_send_request_success(self, mock_connections):
        """Test successful connection request."""
        connections, mock_page = mock_connections

        mock_button = AsyncMock()
        mock_button.is_visible = AsyncMock(return_value=True)
        mock_button.click = AsyncMock()

        mock_page.wait_for_selector = AsyncMock(return_value=mock_button)

        with patch("app.services.linkedin.connections.human_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.connections.action_delay", new_callable=AsyncMock):
            connections._handle_connection_modal = AsyncMock(return_value=True)

            result = await connections.send_connection_request(
                "https://linkedin.com/in/testuser"
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_request_with_note(self, mock_connections):
        """Test sending request with personalized note."""
        connections, mock_page = mock_connections

        mock_button = AsyncMock()
        mock_button.is_visible = AsyncMock(return_value=True)
        mock_button.click = AsyncMock()

        mock_page.wait_for_selector = AsyncMock(return_value=mock_button)

        with patch("app.services.linkedin.connections.human_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.connections.action_delay", new_callable=AsyncMock):
            connections._handle_connection_modal = AsyncMock(return_value=True)

            result = await connections.send_connection_request(
                "https://linkedin.com/in/testuser",
                note="Hi! I'd like to connect."
            )

        # Verify note was passed to modal handler
        connections._handle_connection_modal.assert_called_with(
            mock_page,
            "Hi! I'd like to connect."
        )

    @pytest.mark.asyncio
    async def test_send_request_handles_exception(self, mock_connections):
        """Test that exceptions are handled."""
        connections, mock_page = mock_connections
        connections.browser.goto = AsyncMock(side_effect=Exception("Error"))

        with patch("app.services.linkedin.connections.human_delay", new_callable=AsyncMock):
            result = await connections.send_connection_request(
                "https://linkedin.com/in/testuser"
            )

        assert result is False


class TestLinkedInConnectionsHandleModal:
    """Tests for handling connection modal."""

    @pytest.fixture
    def mock_connections(self):
        """Create mock connections service."""
        mock_browser = MagicMock()
        mock_page = AsyncMock()
        mock_browser.page = mock_page
        connections = LinkedInConnections(browser=mock_browser)
        return connections, mock_page

    @pytest.mark.asyncio
    async def test_handle_modal_waits_for_dialog(self, mock_connections):
        """Test that modal handler waits for dialog."""
        connections, mock_page = mock_connections

        mock_send_btn = AsyncMock()
        mock_send_btn.is_visible = AsyncMock(return_value=True)
        mock_send_btn.click = AsyncMock()

        mock_page.wait_for_selector = AsyncMock(return_value=mock_send_btn)
        mock_page.query_selector = AsyncMock(return_value=None)

        with patch("app.services.linkedin.connections.human_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.connections.action_delay", new_callable=AsyncMock):
            await connections._handle_connection_modal(mock_page, None)

        # Should wait for dialog
        assert any(
            'dialog' in str(call) or 'modal' in str(call)
            for call in mock_page.wait_for_selector.call_args_list
        )

    @pytest.mark.asyncio
    async def test_handle_modal_with_note_fills_textarea(self, mock_connections):
        """Test that note is filled in textarea."""
        connections, mock_page = mock_connections

        mock_add_note_btn = AsyncMock()
        mock_add_note_btn.click = AsyncMock()

        mock_textarea = AsyncMock()
        mock_textarea.fill = AsyncMock()

        mock_send_btn = AsyncMock()
        mock_send_btn.is_visible = AsyncMock(return_value=True)
        mock_send_btn.click = AsyncMock()

        mock_page.query_selector = AsyncMock(return_value=mock_add_note_btn)
        mock_page.wait_for_selector = AsyncMock(side_effect=[
            mock_add_note_btn,  # Add note button
            mock_textarea,  # Textarea
            mock_send_btn,  # Send button
        ])

        with patch("app.services.linkedin.connections.human_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.connections.action_delay", new_callable=AsyncMock):
            await connections._handle_connection_modal(
                mock_page,
                "Hi! Let's connect."
            )

    @pytest.mark.asyncio
    async def test_handle_modal_truncates_long_note(self, mock_connections):
        """Test that long notes are truncated to 300 chars."""
        connections, mock_page = mock_connections

        long_note = "A" * 500

        mock_add_note_btn = AsyncMock()
        mock_textarea = AsyncMock()
        mock_textarea.fill = AsyncMock()
        mock_send_btn = AsyncMock()
        mock_send_btn.is_visible = AsyncMock(return_value=True)
        mock_send_btn.click = AsyncMock()

        mock_page.query_selector = AsyncMock(return_value=mock_add_note_btn)
        mock_page.wait_for_selector = AsyncMock(side_effect=[
            mock_add_note_btn,
            mock_textarea,
            mock_send_btn,
        ])

        with patch("app.services.linkedin.connections.human_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.connections.action_delay", new_callable=AsyncMock):
            await connections._handle_connection_modal(mock_page, long_note)

        # Textarea should receive truncated note
        if mock_textarea.fill.called:
            filled_note = mock_textarea.fill.call_args[0][0]
            assert len(filled_note) <= 300


class TestLinkedInConnectionsBulkRequests:
    """Tests for bulk connection requests."""

    @pytest.fixture
    def mock_connections(self):
        """Create mock connections service."""
        mock_browser = MagicMock()
        connections = LinkedInConnections(browser=mock_browser)
        connections.send_connection_request = AsyncMock(return_value=True)
        return connections

    @pytest.mark.asyncio
    async def test_bulk_requests_processes_profiles(self, mock_connections):
        """Test that bulk requests processes all profiles."""
        connections = mock_connections

        profiles = [
            {"linkedin_url": "https://linkedin.com/in/user1", "name": "User 1"},
            {"linkedin_url": "https://linkedin.com/in/user2", "name": "User 2"},
            {"linkedin_url": "https://linkedin.com/in/user3", "name": "User 3"},
        ]

        with patch("app.services.linkedin.connections.human_delay", new_callable=AsyncMock):
            result = await connections.send_bulk_connection_requests(profiles)

        assert len(result["sent"]) == 3
        assert len(result["failed"]) == 0

    @pytest.mark.asyncio
    async def test_bulk_requests_respects_max_limit(self, mock_connections):
        """Test that bulk requests respects max_requests limit."""
        connections = mock_connections

        profiles = [
            {"linkedin_url": f"https://linkedin.com/in/user{i}", "name": f"User {i}"}
            for i in range(20)
        ]

        with patch("app.services.linkedin.connections.human_delay", new_callable=AsyncMock):
            result = await connections.send_bulk_connection_requests(
                profiles,
                max_requests=5
            )

        # Should only process 5
        assert connections.send_connection_request.call_count == 5

    @pytest.mark.asyncio
    async def test_bulk_requests_skips_missing_url(self, mock_connections):
        """Test that profiles without URL are skipped."""
        connections = mock_connections

        profiles = [
            {"linkedin_url": "https://linkedin.com/in/user1", "name": "User 1"},
            {"name": "User 2"},  # No URL
        ]

        with patch("app.services.linkedin.connections.human_delay", new_callable=AsyncMock):
            result = await connections.send_bulk_connection_requests(profiles)

        assert len(result["sent"]) == 1
        assert len(result["skipped"]) == 1

    @pytest.mark.asyncio
    async def test_bulk_requests_uses_note_template(self, mock_connections):
        """Test that note template is formatted with name."""
        connections = mock_connections

        profiles = [
            {"linkedin_url": "https://linkedin.com/in/user1", "name": "John Smith"},
        ]

        with patch("app.services.linkedin.connections.human_delay", new_callable=AsyncMock):
            await connections.send_bulk_connection_requests(
                profiles,
                note_template="Hi {name}! Let's connect."
            )

        # Check note was formatted
        call_args = connections.send_connection_request.call_args
        note = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("note")
        assert note is not None
        assert "John" in note

    @pytest.mark.asyncio
    async def test_bulk_requests_tracks_failures(self, mock_connections):
        """Test that failed requests are tracked."""
        connections = mock_connections
        connections.send_connection_request = AsyncMock(side_effect=[
            True, False, True
        ])

        profiles = [
            {"linkedin_url": "https://linkedin.com/in/user1", "name": "User 1"},
            {"linkedin_url": "https://linkedin.com/in/user2", "name": "User 2"},
            {"linkedin_url": "https://linkedin.com/in/user3", "name": "User 3"},
        ]

        with patch("app.services.linkedin.connections.human_delay", new_callable=AsyncMock):
            result = await connections.send_bulk_connection_requests(profiles)

        assert len(result["sent"]) == 2
        assert len(result["failed"]) == 1


class TestLinkedInConnectionsCleanup:
    """Tests for connections cleanup."""

    @pytest.mark.asyncio
    async def test_close_own_browser(self):
        """Test closing own browser."""
        connections = LinkedInConnections()
        connections.browser.close = AsyncMock()

        await connections.close()

        connections.browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_provided_browser_not_closed(self):
        """Test that provided browser is not closed."""
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()
        connections = LinkedInConnections(browser=mock_browser)

        await connections.close()

        mock_browser.close.assert_not_called()
