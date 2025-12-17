"""
Job processing service that handles extracting company names from job URLs.

Flow:
1. Check if URL domain is known (in DB or pre-configured platforms)
2. If company site: return saved company name
3. If known platform: extract company from URL pattern
4. If unknown: set job to NEEDS_INPUT status for user to classify
5. When user provides info: learn and save the pattern for future use
"""
import re
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.models.site_selector import SiteSelector, SiteType
from app.models.activity import ActivityLog, ActionType
from app.services.job_parser import (
    JobParser,
    JOB_PLATFORMS,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class JobProcessor:
    """Handles job URL processing and company name extraction."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.parser = JobParser()

    async def process_job(self, job_id: int) -> dict:
        """
        Process a job URL to extract company name.

        Returns dict with:
            - success: bool
            - company_name: str | None
            - needs_input: bool (if user needs to provide company name)
            - message: str
        """
        # Get job from database
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            return {"success": False, "message": f"Job {job_id} not found"}

        # Update status to processing
        job.status = JobStatus.PROCESSING
        await self.db.flush()

        try:
            # Extract domain from URL
            domain = self.parser.extract_domain(job.url)
            if not domain:
                raise ValueError("Could not extract domain from URL")

            logger.info(f"Processing job {job_id} for domain: {domain}")

            # Step 1: Check user-saved site selectors in database
            db_selector = await self._get_db_selector(domain)
            if db_selector:
                return await self._handle_known_site(job, domain, db_selector)

            # Step 2: Check pre-configured job platforms
            is_platform, platform_config = self.parser.is_job_platform(job.url)
            if is_platform and platform_config:
                logger.info(f"Detected pre-configured job platform: {domain}")
                return await self._handle_preconfigured_platform(job, domain, platform_config)

            # Step 3: Unknown domain - need user input
            return await self._request_user_input(job, domain)

        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)

            # Log error
            activity = ActivityLog(
                action_type=ActionType.ERROR,
                description=f"Failed to process job: {e}",
                details={"job_id": job_id, "error": str(e)},
                job_id=job.id,
            )
            self.db.add(activity)

            return {"success": False, "message": str(e)}

    async def _get_db_selector(self, domain: str) -> SiteSelector | None:
        """Get selector for domain from database."""
        result = await self.db.execute(
            select(SiteSelector).where(SiteSelector.domain == domain)
        )
        return result.scalar_one_or_none()

    async def _handle_known_site(
        self, job: Job, domain: str, selector: SiteSelector
    ) -> dict:
        """Handle a URL from a known site (saved in database)."""
        # Update last_used_at
        selector.last_used_at = datetime.utcnow()

        if selector.site_type == SiteType.COMPANY:
            # Company website - use saved company name
            company_name = selector.company_name
            job.company_name = company_name
            job.status = JobStatus.COMPLETED
            job.processed_at = datetime.utcnow()

            activity = ActivityLog(
                action_type=ActionType.COMPANY_EXTRACTED,
                description=f"Company from known site: {company_name}",
                details={
                    "domain": domain,
                    "company_name": company_name,
                    "source": "database",
                    "site_type": "company",
                },
                job_id=job.id,
            )
            self.db.add(activity)

            logger.info(f"Used saved company name: {company_name}")
            return {
                "success": True,
                "company_name": company_name,
                "needs_input": False,
                "message": f"Company from known site: {company_name}",
            }

        else:
            # Platform - extract company from URL pattern
            if selector.url_pattern:
                company_name = self.parser.extract_company_from_url(
                    job.url, selector.url_pattern
                )
                if company_name:
                    job.company_name = company_name
                    job.status = JobStatus.COMPLETED
                    job.processed_at = datetime.utcnow()

                    activity = ActivityLog(
                        action_type=ActionType.COMPANY_EXTRACTED,
                        description=f"Company extracted from platform URL: {company_name}",
                        details={
                            "domain": domain,
                            "company_name": company_name,
                            "platform_name": selector.platform_name,
                            "source": "database",
                            "site_type": "platform",
                        },
                        job_id=job.id,
                    )
                    self.db.add(activity)

                    logger.info(f"Extracted company from platform URL: {company_name}")
                    return {
                        "success": True,
                        "company_name": company_name,
                        "platform": selector.platform_name,
                        "needs_input": False,
                        "message": f"Company extracted: {company_name}",
                    }

            # URL pattern didn't match - request user input
            logger.warning(f"URL pattern didn't match for platform: {domain}")
            return await self._request_user_input(job, domain)

    async def _handle_preconfigured_platform(
        self, job: Job, domain: str, platform_config: dict
    ) -> dict:
        """Handle job URLs from pre-configured platforms (greenhouse, lever, etc.)."""
        company_name = None

        # Extract company from URL pattern
        if "company_from_url" in platform_config:
            company_name = self.parser.extract_company_from_url(
                job.url, platform_config["company_from_url"]
            )

        if company_name:
            job.company_name = company_name
            job.status = JobStatus.COMPLETED
            job.processed_at = datetime.utcnow()

            activity = ActivityLog(
                action_type=ActionType.COMPANY_EXTRACTED,
                description=f"Extracted company from platform URL: {company_name}",
                details={
                    "domain": domain,
                    "company_name": company_name,
                    "platform": True,
                    "source": "preconfigured",
                },
                job_id=job.id,
            )
            self.db.add(activity)

            logger.info(f"Extracted company from pre-configured platform URL: {company_name}")
            return {
                "success": True,
                "company_name": company_name,
                "needs_input": False,
                "platform": domain,
                "message": f"Company extracted from URL: {company_name}",
            }

        # Could not extract from URL - request user input
        logger.warning(f"Could not extract company from platform URL: {domain}")
        return await self._request_user_input(job, domain, is_known_platform=True)

    async def _request_user_input(
        self, job: Job, domain: str, is_known_platform: bool = False
    ) -> dict:
        """Set job to needs_input status when we can't extract company automatically."""
        job.status = JobStatus.NEEDS_INPUT

        # Log activity
        activity = ActivityLog(
            action_type=ActionType.COMPANY_INPUT_NEEDED,
            description=f"Unknown job site: {domain}. User input needed.",
            details={
                "domain": domain,
                "url": job.url,
                "is_known_platform": is_known_platform,
            },
            job_id=job.id,
        )
        self.db.add(activity)

        logger.info(f"Job {job.id} needs user input for domain: {domain}")
        return {
            "success": True,
            "needs_input": True,
            "domain": domain,
            "is_known_platform": is_known_platform,
            "message": f"Unknown job site ({domain}). Please provide the company name.",
        }

    async def submit_company_info(
        self,
        job_id: int,
        company_name: str,
        site_type: str,  # "company" or "platform"
        platform_name: str | None = None,
    ) -> dict:
        """
        Handle user submitting company info for a job.
        Learns and saves the URL pattern for future use.
        """
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            return {"success": False, "message": f"Job {job_id} not found"}

        if job.status != JobStatus.NEEDS_INPUT:
            return {
                "success": False,
                "message": f"Job is not waiting for input (status: {job.status})",
            }

        # Update job with company name
        job.company_name = company_name
        job.status = JobStatus.COMPLETED
        job.processed_at = datetime.utcnow()

        domain = self.parser.extract_domain(job.url)

        # Learn and save the pattern
        if domain:
            await self._learn_site_pattern(
                domain=domain,
                url=job.url,
                company_name=company_name,
                site_type=site_type,
                platform_name=platform_name,
            )

        # Log activity
        activity = ActivityLog(
            action_type=ActionType.COMPANY_EXTRACTED,
            description=f"Company provided by user: {company_name}",
            details={
                "domain": domain,
                "company_name": company_name,
                "site_type": site_type,
                "platform_name": platform_name,
                "user_provided": True,
            },
            job_id=job.id,
        )
        self.db.add(activity)

        logger.info(f"Job {job_id} completed with user-provided company: {company_name}")
        return {
            "success": True,
            "company_name": company_name,
            "message": f"Company name saved: {company_name}",
        }

    async def _learn_site_pattern(
        self,
        domain: str,
        url: str,
        company_name: str,
        site_type: str,
        platform_name: str | None = None,
    ):
        """Learn and save URL pattern for a site."""
        # Check if already exists
        result = await self.db.execute(
            select(SiteSelector).where(SiteSelector.domain == domain)
        )
        existing = result.scalar_one_or_none()

        site_type_enum = SiteType.PLATFORM if site_type == "platform" else SiteType.COMPANY

        # Generate URL pattern for platforms
        url_pattern = None
        if site_type == "platform":
            url_pattern = self._generate_url_pattern(url, company_name)

        if existing:
            # Update existing
            existing.site_type = site_type_enum
            existing.company_name = company_name
            existing.platform_name = platform_name
            existing.url_pattern = url_pattern
            existing.example_url = url
            existing.example_company = company_name
            logger.info(f"Updated site pattern for domain: {domain}")
        else:
            # Create new
            selector = SiteSelector(
                domain=domain,
                site_type=site_type_enum,
                company_name=company_name,
                platform_name=platform_name,
                url_pattern=url_pattern,
                example_url=url,
                example_company=company_name,
            )
            self.db.add(selector)

            # Log activity
            activity = ActivityLog(
                action_type=ActionType.SELECTOR_LEARNED,
                description=f"Learned pattern for domain: {domain} ({site_type})",
                details={
                    "domain": domain,
                    "site_type": site_type,
                    "platform_name": platform_name,
                    "url_pattern": url_pattern,
                },
            )
            self.db.add(activity)
            logger.info(f"Created new site pattern for domain: {domain}")

    def _generate_url_pattern(self, url: str, company_name: str) -> str | None:
        """
        Generate a regex pattern to extract company name from URL.

        Analyzes the URL to find where the company name appears and creates
        a pattern that can extract it from similar URLs.
        """
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)

            # Normalize company name for matching (lowercase, no spaces/hyphens)
            company_normalized = company_name.lower().replace(" ", "").replace("-", "").replace("_", "")

            # Check subdomain
            host_parts = parsed.netloc.split(".")
            if len(host_parts) > 2:
                subdomain = host_parts[0].lower()
                subdomain_normalized = subdomain.replace("-", "").replace("_", "")
                if subdomain_normalized == company_normalized or company_normalized in subdomain_normalized:
                    # Company is in subdomain: pattern like "([^.]+).domain.com"
                    base_domain = ".".join(host_parts[1:])
                    pattern = rf"([^.]+)\.{re.escape(base_domain)}"
                    logger.info(f"Generated subdomain pattern: {pattern}")
                    return pattern

            # Check URL path segments
            path_parts = [p for p in parsed.path.split("/") if p]
            for i, part in enumerate(path_parts):
                part_normalized = part.lower().replace("-", "").replace("_", "")
                if part_normalized == company_normalized or company_normalized in part_normalized:
                    # Company is in this path segment
                    # Build pattern: domain/path1/path2/([^/]+)/...
                    domain_escaped = re.escape(parsed.netloc)
                    prefix_parts = path_parts[:i]
                    prefix = "/".join(prefix_parts)
                    if prefix:
                        pattern = rf"{domain_escaped}/{prefix}/([^/]+)"
                    else:
                        pattern = rf"{domain_escaped}/([^/]+)"
                    logger.info(f"Generated path pattern: {pattern}")
                    return pattern

            # Fallback: try to find company name directly in URL
            company_variants = [
                company_name.lower(),
                company_name.lower().replace(" ", "-"),
                company_name.lower().replace(" ", "_"),
                company_name.lower().replace(" ", ""),
            ]

            url_lower = url.lower()
            for variant in company_variants:
                if variant in url_lower:
                    # Found it - try to build a pattern
                    # This is a basic fallback
                    idx = url_lower.find(variant)
                    before = url[:idx]
                    after = url[idx + len(variant):]

                    # Find the boundaries (/, ., -, _, or end)
                    pattern = re.escape(before) + r"([^/.\-_]+)"
                    logger.info(f"Generated fallback pattern: {pattern}")
                    return pattern

            logger.warning(f"Could not generate URL pattern for: {url}")
            return None

        except Exception as e:
            logger.error(f"Error generating URL pattern: {e}")
            return None

    # Legacy method for backward compatibility
    async def submit_company_name(
        self,
        job_id: int,
        company_name: str,
        company_selector: str | None = None,
    ) -> dict:
        """Legacy method - redirects to submit_company_info."""
        return await self.submit_company_info(
            job_id=job_id,
            company_name=company_name,
            site_type="company",  # Default to company for legacy calls
        )


async def process_job_background(job_id: int, db: AsyncSession):
    """Background task wrapper for job processing."""
    processor = JobProcessor(db)
    await processor.process_job(job_id)
    await db.commit()
