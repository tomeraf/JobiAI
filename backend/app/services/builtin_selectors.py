"""
Built-in site selectors bundled with JobiAI.

These are seeded into the database on first startup to provide
out-of-the-box support for common job sites.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site_selector import SiteSelector, SiteType
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Format: domain -> {site_type, company_name, platform_name, url_pattern, example_company}
# site_type: "company" (direct company career page) or "platform" (hosts multiple companies)

BUILTIN_SITE_SELECTORS = {
    # === Company Career Pages ===
    # These map directly to a company name
    "agorareal.com": {
        "site_type": "company",
        "company_name": "agora",
    },
    "amazon.jobs": {
        "site_type": "company",
        "company_name": "amazon",
    },
    "careers.cisco.com": {
        "site_type": "company",
        "company_name": "cisco",
    },
    "careers.eladsoft.com": {
        "site_type": "company",
        "company_name": "elad",
    },
    "careers.ibm.com": {
        "site_type": "company",
        "company_name": "IBM",
    },
    "careers.qualitestgroup.com": {
        "site_type": "company",
        "company_name": "qualitest",
    },
    "careers.riverside.com": {
        "site_type": "company",
        "company_name": "riverside",
    },
    "catonetworks.com": {
        "site_type": "company",
        "company_name": "cato",
    },
    "dotcompliance.com": {
        "site_type": "company",
        "company_name": "Dot Compliance",
    },
    "elbitsystemscareer.com": {
        "site_type": "company",
        "company_name": "elbit",
    },
    "fullpath.com": {
        "site_type": "company",
        "company_name": "Fullpath",
    },
    "global-e.com": {
        "site_type": "company",
        "company_name": "global e",
    },
    "homedepot.com": {
        "site_type": "company",
        "company_name": "home depot",
    },
    "imagry.co": {
        "site_type": "company",
        "company_name": "imagry",
    },
    "jobs.sap.com": {
        "site_type": "company",
        "company_name": "sap",
    },
    "kmslh.com": {
        "site_type": "company",
        "company_name": "KMS",
    },
    "mccann.co.il": {
        "site_type": "company",
        "company_name": "McCANN",
    },
    "nanit.com": {
        "site_type": "company",
        "company_name": "nanit",
    },
    "nayax.com": {
        "site_type": "company",
        "company_name": "nayax",
    },
    "papaya.com": {
        "site_type": "company",
        "company_name": "papaya",
    },
    "rapyd.net": {
        "site_type": "company",
        "company_name": "rapyd",
    },
    "superplay.co": {
        "site_type": "company",
        "company_name": "super play",
    },
    "surecomp.com": {
        "site_type": "company",
        "company_name": "surecomp",
    },
    "tailorbrands.com": {
        "site_type": "company",
        "company_name": "Tailor Brands",
    },
    "tailormed.co": {
        "site_type": "company",
        "company_name": "tailormed",
    },
    "waterfall-security.com": {
        "site_type": "company",
        "company_name": "waterfall",
    },
    # === Job Platforms ===
    # These extract company name from URL pattern
    "comeet.com": {
        "site_type": "platform",
        "platform_name": "comeet",
        "url_pattern": r"www\.comeet\.com/jobs/([^/]+)",
    },
    "job-boards.eu.greenhouse.io": {
        "site_type": "platform",
        "platform_name": "greenhouse",
        "url_pattern": r"job\-boards\.eu\.greenhouse\.io/([^/]+)",
    },
    "jobs.eu.lever.co": {
        "site_type": "platform",
        "platform_name": "lever",
        "url_pattern": r"jobs\.eu\.lever\.co/([^/]+)",
    },
}


async def seed_builtin_selectors(db: AsyncSession) -> int:
    """
    Seed built-in site selectors into the database.

    Only adds selectors that don't already exist (by domain).
    This runs on startup to ensure new users get the bundled selectors.

    Returns:
        Number of selectors added
    """
    added = 0

    for domain, config in BUILTIN_SITE_SELECTORS.items():
        # Check if already exists
        result = await db.execute(
            select(SiteSelector).where(SiteSelector.domain == domain)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Don't overwrite user's customizations
            continue

        # Create new selector
        site_type = SiteType.PLATFORM if config["site_type"] == "platform" else SiteType.COMPANY

        selector = SiteSelector(
            domain=domain,
            site_type=site_type,
            company_name=config.get("company_name"),
            platform_name=config.get("platform_name"),
            url_pattern=config.get("url_pattern"),
            example_company=config.get("company_name"),
        )
        db.add(selector)
        added += 1

    if added > 0:
        await db.commit()
        logger.info(f"Seeded {added} built-in site selectors")

    return added
