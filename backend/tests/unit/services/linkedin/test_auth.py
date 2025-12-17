"""
Unit tests for LinkedInAuth service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.linkedin.auth import LinkedInAuth, LINKEDIN_LOGIN_URL, LINKEDIN_FEED_URL


class TestLinkedInAuthConstants:
    """Tests for auth constants."""

    def test_login_url_is_linkedin(self):
        """Test that login URL is LinkedIn."""
        assert "linkedin.com" in LINKEDIN_LOGIN_URL
        assert "login" in LINKEDIN_LOGIN_URL

    def test_feed_url_is_linkedin(self):
        """Test that feed URL is LinkedIn."""
        assert "linkedin.com" in LINKEDIN_FEED_URL
        assert "feed" in LINKEDIN_FEED_URL


class TestLinkedInAuthInitialization:
    """Tests for auth initialization."""

    def test_auth_creates_browser(self):
        """Test that auth creates a browser instance."""
        auth = LinkedInAuth()
        assert auth.browser is not None


class TestLinkedInAuthCheckSession:
    """Tests for session checking."""

    @pytest.fixture
    def mock_browser(self):
        """Create mock browser."""
        mock = MagicMock()
        mock.has_saved_session = MagicMock(return_value=True)
        mock.goto = AsyncMock()
        mock.close = AsyncMock()

        mock_page = MagicMock()
        mock_page.url = LINKEDIN_FEED_URL
        mock_page.wait_for_selector = AsyncMock()
        mock.page = mock_page
        mock.initialize = AsyncMock(return_value=mock_page)

        return mock

    @pytest.mark.asyncio
    async def test_check_session_no_saved_session(self):
        """Test check_session returns False when no saved session."""
        auth = LinkedInAuth()
        auth.browser.has_saved_session = MagicMock(return_value=False)

        result = await auth.check_session()
        assert result is False

    @pytest.mark.asyncio
    async def test_check_session_valid_session(self, mock_browser):
        """Test check_session returns True for valid session."""
        auth = LinkedInAuth()
        auth.browser = mock_browser

        result = await auth.check_session()
        assert result is True
        mock_browser.initialize.assert_called_once_with(headless=True)

    @pytest.mark.asyncio
    async def test_check_session_redirected_to_login(self, mock_browser):
        """Test check_session returns False when redirected to login."""
        auth = LinkedInAuth()
        mock_browser.page.url = "https://www.linkedin.com/login"
        auth.browser = mock_browser

        result = await auth.check_session()
        assert result is False

    @pytest.mark.asyncio
    async def test_check_session_redirected_to_checkpoint(self, mock_browser):
        """Test check_session returns False on security checkpoint."""
        auth = LinkedInAuth()
        mock_browser.page.url = "https://www.linkedin.com/checkpoint/challenge"
        auth.browser = mock_browser

        result = await auth.check_session()
        assert result is False

    @pytest.mark.asyncio
    async def test_check_session_handles_exception(self, mock_browser):
        """Test check_session handles exceptions gracefully."""
        auth = LinkedInAuth()
        mock_browser.initialize = AsyncMock(side_effect=Exception("Connection error"))
        auth.browser = mock_browser

        result = await auth.check_session()
        assert result is False


class TestLinkedInAuthLogin:
    """Tests for login flow."""

    @pytest.fixture
    def mock_browser_for_login(self):
        """Create mock browser for login tests."""
        mock = MagicMock()
        mock.goto = AsyncMock()
        mock.save_session = AsyncMock()
        mock.close = AsyncMock()

        mock_page = MagicMock()
        mock_page.url = LINKEDIN_LOGIN_URL
        mock.page = mock_page
        mock.initialize = AsyncMock(return_value=mock_page)

        return mock

    @pytest.mark.asyncio
    async def test_login_opens_visible_browser(self, mock_browser_for_login):
        """Test that login opens visible browser."""
        auth = LinkedInAuth()
        auth.browser = mock_browser_for_login

        # Don't wait for login
        await auth.login(wait_for_manual_login=False)

        mock_browser_for_login.initialize.assert_called_once_with(headless=False)

    @pytest.mark.asyncio
    async def test_login_navigates_to_login_page(self, mock_browser_for_login):
        """Test that login navigates to login page."""
        auth = LinkedInAuth()
        auth.browser = mock_browser_for_login

        await auth.login(wait_for_manual_login=False)

        mock_browser_for_login.goto.assert_called_once_with(LINKEDIN_LOGIN_URL)

    @pytest.mark.asyncio
    async def test_login_no_wait_returns_false(self, mock_browser_for_login):
        """Test that login without waiting returns False."""
        auth = LinkedInAuth()
        auth.browser = mock_browser_for_login

        result = await auth.login(wait_for_manual_login=False)
        assert result is False

    @pytest.mark.asyncio
    async def test_login_detects_successful_login(self, mock_browser_for_login):
        """Test that login detects successful authentication."""
        auth = LinkedInAuth()
        auth.browser = mock_browser_for_login

        # Simulate successful login by changing URL to feed
        mock_browser_for_login.page.url = LINKEDIN_FEED_URL

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch("app.services.linkedin.auth.human_delay", new_callable=AsyncMock):
                result = await auth.login(wait_for_manual_login=True)

        assert result is True
        mock_browser_for_login.save_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_handles_exception(self, mock_browser_for_login):
        """Test that login handles exceptions."""
        auth = LinkedInAuth()
        mock_browser_for_login.initialize = AsyncMock(side_effect=Exception("Error"))
        auth.browser = mock_browser_for_login

        result = await auth.login()
        assert result is False


class TestLinkedInAuthProfileInfo:
    """Tests for profile info retrieval."""

    @pytest.fixture
    def mock_browser_with_profile(self):
        """Create mock browser with profile elements."""
        mock = MagicMock()
        mock.initialize = AsyncMock()
        mock.goto = AsyncMock()

        mock_page = AsyncMock()

        mock_name_elem = AsyncMock()
        mock_name_elem.inner_text = AsyncMock(return_value="John Doe")
        mock_page.wait_for_selector = AsyncMock(return_value=mock_name_elem)
        mock_page.query_selector = AsyncMock(return_value=mock_name_elem)

        mock.page = mock_page
        return mock

    @pytest.mark.asyncio
    async def test_get_profile_info_returns_name(self, mock_browser_with_profile):
        """Test getting profile info returns name."""
        auth = LinkedInAuth()
        auth.browser = mock_browser_with_profile

        profile = await auth.get_profile_info()

        assert "name" in profile
        assert profile["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_get_profile_info_handles_missing_name(self):
        """Test profile info handles missing name element."""
        auth = LinkedInAuth()
        mock = MagicMock()
        mock.initialize = AsyncMock()
        mock.goto = AsyncMock()

        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))
        mock_page.query_selector = AsyncMock(return_value=None)
        mock.page = mock_page

        auth.browser = mock

        profile = await auth.get_profile_info()
        assert isinstance(profile, dict)

    @pytest.mark.asyncio
    async def test_get_profile_info_handles_exception(self):
        """Test profile info handles exceptions."""
        auth = LinkedInAuth()
        mock = MagicMock()
        mock.page = None
        mock.initialize = AsyncMock(side_effect=Exception("Error"))
        auth.browser = mock

        profile = await auth.get_profile_info()
        assert profile == {}


class TestLinkedInAuthCleanup:
    """Tests for auth cleanup."""

    @pytest.mark.asyncio
    async def test_clear_session(self):
        """Test clearing session."""
        auth = LinkedInAuth()
        auth.browser.clear_session = AsyncMock()

        await auth.clear_session()

        auth.browser.clear_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing auth and browser."""
        auth = LinkedInAuth()
        auth.browser.close = AsyncMock()

        await auth.close()

        auth.browser.close.assert_called_once()
