"""
LinkedIn messaging service using linkedin-api library.
"""
from app.services.linkedin.client import get_linkedin_client
from app.services.gender_detector import detect_gender
from app.utils.logger import get_logger
from app.utils.delays import human_delay

logger = get_logger(__name__)


class LinkedInMessaging:
    """Handles LinkedIn messaging to connections."""

    def __init__(self):
        self.client = get_linkedin_client()

    async def send_message(
        self,
        profile_url: str = None,
        public_id: str = None,
        urn_id: str = None,
        message: str = "",
    ) -> bool:
        """
        Send a direct message to a LinkedIn connection.

        Args:
            profile_url: URL of the profile to message
            public_id: Public ID of the recipient
            urn_id: URN ID of the recipient
            message: The message content to send

        Returns:
            True if message sent successfully
        """
        # Extract public_id from URL if needed
        if profile_url and not public_id:
            public_id = self._extract_public_id(profile_url)

        return await self.client.send_message(
            urn_id=urn_id,
            public_id=public_id,
            message=message,
        )

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

    async def send_gendered_message(
        self,
        profile_url: str,
        name: str,
        company: str,
        template_male: str,
        template_female: str,
        template_neutral: str,
        known_gender: str | None = None,
        urn_id: str | None = None,
    ) -> tuple[bool, str]:
        """
        Send a gender-appropriate message.

        Args:
            profile_url: LinkedIn profile URL
            name: Person's name
            company: Company name for template
            template_male: Message template for males
            template_female: Message template for females
            template_neutral: Fallback template
            known_gender: Pre-determined gender if available
            urn_id: URN ID if available

        Returns:
            Tuple of (success, gender_used)
        """
        # Detect gender if not provided
        gender = known_gender or detect_gender(name)

        # Select appropriate template
        if gender == "male":
            template = template_male
        elif gender == "female":
            template = template_female
        else:
            template = template_neutral

        # Format message with variables
        try:
            # Use first name only
            first_name = name.split()[0] if name else ""
            message = template.format(name=first_name, company=company)
        except KeyError as e:
            logger.error(f"Template format error: {e}")
            message = template  # Use template as-is if formatting fails

        # Send the message
        public_id = self._extract_public_id(profile_url) if profile_url else None
        success = await self.client.send_message(
            urn_id=urn_id,
            public_id=public_id,
            message=message,
        )

        return success, gender

    async def send_bulk_messages(
        self,
        contacts: list[dict],
        template_male: str,
        template_female: str,
        template_neutral: str,
        company: str,
    ) -> dict:
        """
        Send messages to multiple contacts.

        Args:
            contacts: List of contact dicts with 'linkedin_url', 'name', 'gender', 'urn_id'
            template_*: Message templates
            company: Company name for template

        Returns:
            Results dict with sent/failed/skipped lists
        """
        results = {
            "sent": [],
            "failed": [],
            "skipped": [],
        }

        for i, contact in enumerate(contacts):
            url = contact.get("linkedin_url")
            name = contact.get("name", "")
            gender = contact.get("gender")
            urn_id = contact.get("urn_id")

            if not url and not urn_id:
                results["skipped"].append(contact)
                continue

            # Check if already messaged
            if contact.get("message_sent_at"):
                logger.info(f"Skipping {name} - already messaged")
                results["skipped"].append(contact)
                continue

            success, detected_gender = await self.send_gendered_message(
                profile_url=url,
                name=name,
                company=company,
                template_male=template_male,
                template_female=template_female,
                template_neutral=template_neutral,
                known_gender=gender,
                urn_id=urn_id,
            )

            if success:
                contact["detected_gender"] = detected_gender
                results["sent"].append(contact)
            else:
                results["failed"].append(contact)

            # Delay between messages to avoid rate limiting
            if i < len(contacts) - 1:
                await human_delay(3, 6)

        logger.info(
            f"Bulk messaging results: "
            f"{len(results['sent'])} sent, "
            f"{len(results['failed'])} failed, "
            f"{len(results['skipped'])} skipped"
        )

        return results
