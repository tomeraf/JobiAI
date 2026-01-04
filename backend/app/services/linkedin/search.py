"""
LinkedIn search service using linkedin-api library.
"""
from app.services.linkedin.client import get_linkedin_client
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LinkedInSearch:
    """Handles LinkedIn search and connection discovery."""

    def __init__(self):
        self.client = get_linkedin_client()

    async def search_connections_by_company(self, company: str) -> list[dict]:
        """
        Search through existing connections for people at a specific company.

        Args:
            company: Company name to search for

        Returns:
            List of connection profiles found
        """
        return await self.client.search_connections_by_company(company)

    async def search_people_at_company(
        self,
        company: str,
        limit: int = 15
    ) -> list[dict]:
        """
        Search LinkedIn for people at a company (not necessarily connections).

        Args:
            company: Company name to search for
            limit: Maximum results to return

        Returns:
            List of people profiles
        """
        return await self.client.search_people(
            keywords=company,
            limit=limit,
        )

    async def get_connections(self, limit: int = 100) -> list[dict]:
        """
        Get the user's connections.

        Args:
            limit: Maximum connections to fetch

        Returns:
            List of connection profiles
        """
        return await self.client.get_connections(limit=limit)

    async def get_profile(self, public_id: str) -> dict | None:
        """
        Get a profile by public ID.

        Args:
            public_id: The LinkedIn public ID (from URL)

        Returns:
            Profile dict or None
        """
        return await self.client.get_profile(public_id)

    async def search_company_all_degrees(self, company: str, limit: int = 15, message_generator=None, first_degree_only: bool = False) -> dict:
        """
        Search for people at a company - first 1st degree, then 2nd, then 3rd+ if needed.
        All in a single browser session for efficiency.

        Args:
            company: Company name to search for
            limit: Maximum results to return per degree level
            message_generator: Optional function(name, company) -> str to generate message text
                              for 1st degree connections
            first_degree_only: If True, only search for 1st degree connections (don't fall back to 2nd/3rd)

        Returns:
            Dict with 'first_degree', 'second_degree', 'third_plus', and 'messages_sent' lists
        """
        return await self.client.search_company_all_degrees(company, limit, message_generator, first_degree_only)
