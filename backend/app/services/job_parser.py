import re
from urllib.parse import urlparse

from app.utils.logger import get_logger

logger = get_logger(__name__)


# Job platforms that host jobs for multiple companies
# These need special handling - company is extracted from URL path/subdomain
JOB_PLATFORMS = {
    "greenhouse.io": {
        "type": "platform",
        "company_from_url": r"boards\.greenhouse\.io/([^/]+)",
    },
    "boards.greenhouse.io": {
        "type": "platform",
        "company_from_url": r"boards\.greenhouse\.io/([^/]+)",
    },
    "lever.co": {
        "type": "platform",
        "company_from_url": r"jobs\.lever\.co/([^/]+)",
    },
    "jobs.lever.co": {
        "type": "platform",
        "company_from_url": r"jobs\.lever\.co/([^/]+)",
    },
    "myworkdayjobs.com": {
        "type": "platform",
        "company_from_url": r"://([^.]+)\.wd\d*\.myworkdayjobs\.com",
    },
    "ashbyhq.com": {
        "type": "platform",
        "company_from_url": r"jobs\.ashbyhq\.com/([^/]+)",
    },
    "jobs.ashbyhq.com": {
        "type": "platform",
        "company_from_url": r"jobs\.ashbyhq\.com/([^/]+)",
    },
    "smartrecruiters.com": {
        "type": "platform",
        "company_from_url": r"jobs\.smartrecruiters\.com/([^/]+)",
    },
    "jobs.smartrecruiters.com": {
        "type": "platform",
        "company_from_url": r"jobs\.smartrecruiters\.com/([^/]+)",
    },
    "breezy.hr": {
        "type": "platform",
        "company_from_url": r"://([^.]+)\.breezy\.hr",
    },
    "applytojob.com": {
        "type": "platform",
        "company_from_url": r"://([^.]+)\.applytojob\.com",
    },
    "recruitee.com": {
        "type": "platform",
        "company_from_url": r"://([^.]+)\.recruitee\.com",
    },
    "bamboohr.com": {
        "type": "platform",
        "company_from_url": r"://([^.]+)\.bamboohr\.com",
    },
    "icims.com": {
        "type": "platform",
        "company_from_url": r"://careers-([^.]+)\.icims\.com",
    },
}


class JobParser:
    """Parses job URLs to extract company information."""

    def __init__(self):
        pass

    def extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""

    def is_job_platform(self, url: str) -> tuple[bool, dict | None]:
        """
        Check if URL is from a known job platform.

        Returns:
            Tuple of (is_platform, platform_config)
        """
        domain = self.extract_domain(url)

        # Check exact domain match
        if domain in JOB_PLATFORMS:
            return True, JOB_PLATFORMS[domain]

        # Check if domain ends with any platform domain
        for platform_domain, config in JOB_PLATFORMS.items():
            if domain.endswith(platform_domain):
                return True, config

        return False, None

    def extract_company_from_url(self, url: str, pattern: str) -> str | None:
        """
        Extract company name from URL using regex pattern.

        Used for job platforms where company is in the URL path/subdomain.
        """
        try:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                company = match.group(1)
                # Clean up: replace hyphens/underscores with spaces, title case
                company = company.replace("-", " ").replace("_", " ")
                company = company.title()
                logger.info(f"Extracted company from URL: {company}")
                return company
        except Exception as e:
            logger.warning(f"Could not extract company from URL: {e}")
        return None


def get_job_platform(url: str) -> tuple[bool, dict | None]:
    """
    Check if URL is from a known job platform.

    Returns:
        Tuple of (is_platform, platform_config)
    """
    parser = JobParser()
    return parser.is_job_platform(url)


def extract_company_from_platform_url(url: str) -> str | None:
    """
    Extract company name from a job platform URL.

    Returns company name if extracted, None otherwise.
    """
    parser = JobParser()
    is_platform, config = parser.is_job_platform(url)

    if is_platform and config and "company_from_url" in config:
        return parser.extract_company_from_url(url, config["company_from_url"])

    return None
