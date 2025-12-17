"""
LinkedIn connection requests service using linkedin-api library.
"""
from app.services.linkedin.client import get_linkedin_client
from app.utils.logger import get_logger
from app.utils.delays import human_delay

logger = get_logger(__name__)


class LinkedInConnections:
    """Handles LinkedIn connection requests."""

    def __init__(self):
        self.client = get_linkedin_client()

    def _extract_public_id(self, profile_url: str) -> str | None:
        """Extract public_id from LinkedIn profile URL."""
        try:
            # Handle URLs like https://www.linkedin.com/in/john-doe/
            if "/in/" in profile_url:
                parts = profile_url.split("/in/")
                if len(parts) > 1:
                    public_id = parts[1].strip("/").split("?")[0]
                    return public_id
        except Exception as e:
            logger.error(f"Error extracting public_id from URL: {e}")
        return None

    async def send_connection_request(
        self,
        profile_url: str = None,
        public_id: str = None,
        note: str | None = None,
    ) -> bool:
        """
        Send a connection request to a LinkedIn profile.

        Args:
            profile_url: URL of the profile to connect with
            public_id: Public ID of the profile
            note: Optional personalized note (max 300 chars)

        Returns:
            True if request sent successfully
        """
        # Extract public_id from URL if needed
        if profile_url and not public_id:
            public_id = self._extract_public_id(profile_url)

        return await self.client.send_connection_request(
            public_id=public_id,
            message=note,
        )

    async def send_bulk_connection_requests(
        self,
        profiles: list[dict],
        note_template: str | None = None,
        max_requests: int = 15
    ) -> dict:
        """
        Send connection requests to multiple profiles.

        Args:
            profiles: List of profile dicts with 'linkedin_url', 'public_id', 'urn_id', 'name'
            note_template: Optional note template with {name} placeholder
            max_requests: Maximum number of requests to send

        Returns:
            Dict with success/failure counts
        """
        results = {
            "sent": [],
            "failed": [],
            "skipped": [],
        }

        for i, profile in enumerate(profiles[:max_requests]):
            url = profile.get("linkedin_url")
            public_id = profile.get("public_id")
            urn_id = profile.get("urn_id")
            name = profile.get("name", "")

            if not url and not public_id and not urn_id:
                results["skipped"].append(profile)
                continue

            # Format note if template provided
            note = None
            if note_template:
                try:
                    note = note_template.format(name=name.split()[0])  # First name only
                except Exception:
                    note = note_template

            # Send request
            success = await self.send_connection_request(
                profile_url=url,
                public_id=public_id,
                note=note,
            )

            if success:
                results["sent"].append(profile)
            else:
                results["failed"].append(profile)

            # Delay between requests to avoid rate limiting
            if i < len(profiles) - 1:
                await human_delay(3, 6)

        logger.info(
            f"Bulk connection results: "
            f"{len(results['sent'])} sent, "
            f"{len(results['failed'])} failed, "
            f"{len(results['skipped'])} skipped"
        )

        return results
