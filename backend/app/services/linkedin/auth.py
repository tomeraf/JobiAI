"""
LinkedIn authentication service using linkedin-api library.
"""
from app.services.linkedin.client import get_linkedin_client
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LinkedInAuth:
    """Handles LinkedIn authentication and session management."""

    def __init__(self):
        self.client = get_linkedin_client()

    async def check_session(self) -> bool:
        """Check if we have a valid LinkedIn session."""
        return await self.client.check_session()

    async def login(self, email: str, password: str) -> bool:
        """
        Authenticate with LinkedIn using email and password.

        Args:
            email: LinkedIn email
            password: LinkedIn password

        Returns:
            True if login successful
        """
        return await self.client.login(email, password)

    async def login_with_browser(self) -> bool:
        """
        Open a browser window for manual LinkedIn login.

        This opens a browser, lets you login manually, then captures
        the cookies to use with the linkedin-api.

        Returns:
            True if login successful
        """
        return await self.client.login_with_browser()

    async def login_with_saved_credentials(self) -> bool:
        """Attempt to login using saved credentials."""
        return await self.client.login_with_saved_credentials()

    async def get_profile_info(self) -> dict:
        """Get basic profile info of logged-in user."""
        return await self.client.get_profile_info()

    async def clear_session(self):
        """Clear saved session data."""
        await self.client.logout()

    @property
    def is_logged_in(self) -> bool:
        """Check if currently logged in."""
        return self.client.is_logged_in
