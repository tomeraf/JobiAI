"""
Person data extraction from LinkedIn search results.

Centralized logic for extracting name, headline, and profile URL from search result elements.
"""

import re
from app.utils.logger import get_logger
from .selectors import LinkedInSelectors

logger = get_logger(__name__)


def clean_name(name: str) -> str:
    """
    Clean extracted name by removing degree indicators and extra whitespace.

    LinkedIn's new UI (2026) includes degree indicators like "• 1st", "• 2nd", "• 3rd+"
    in the same paragraph as the name.

    Args:
        name: Raw name text from LinkedIn

    Returns:
        Cleaned name without degree indicators
    """
    if not name:
        return ""
    # Remove degree indicators like "• 1st", "• 2nd", "• 3rd+", "• 3rd"
    cleaned = re.sub(r'\s*•\s*(1st|2nd|3rd\+?)\s*$', '', name)
    # Also handle case where it's at the beginning or middle (shouldn't happen but just in case)
    cleaned = re.sub(r'\s*•\s*(1st|2nd|3rd\+?)\s*', ' ', cleaned)
    return cleaned.strip()


def extract_text_from_element(element, selectors: list[str]) -> str:
    """
    Try multiple selectors to extract text from an element.

    Args:
        element: Playwright element to search within
        selectors: List of CSS selectors to try

    Returns:
        Extracted text or empty string
    """
    for selector in selectors:
        try:
            el = element.query_selector(selector)
            if el:
                text = el.inner_text().strip()
                if text:
                    return text
        except Exception:
            continue
    return ""


def extract_attribute_from_element(element, selectors: list[str], attribute: str) -> str:
    """
    Try multiple selectors to extract an attribute from an element.

    Args:
        element: Playwright element to search within
        selectors: List of CSS selectors to try
        attribute: Attribute name to extract

    Returns:
        Extracted attribute value or empty string
    """
    for selector in selectors:
        try:
            el = element.query_selector(selector)
            if el:
                value = el.get_attribute(attribute) or ""
                if value:
                    return value
        except Exception:
            continue
    return ""


def extract_public_id(url: str) -> str:
    """
    Extract LinkedIn public_id from a profile URL.

    Args:
        url: LinkedIn profile URL (e.g., "https://www.linkedin.com/in/john-doe?...")

    Returns:
        Public ID (e.g., "john-doe") or empty string
    """
    if "/in/" not in url:
        return ""
    return url.split("/in/")[1].split("/")[0].split("?")[0]


def extract_person_from_search_result(result, company_filter: str = None) -> dict | None:
    """
    Extract person information from a LinkedIn search result element.

    Args:
        result: Playwright element representing a search result
        company_filter: Optional company name to filter by (checks headline and current job)

    Returns:
        Dict with name, headline, linkedin_url, public_id, or None if extraction failed
    """
    try:
        # New LinkedIn UI (2026): Get all paragraphs and use by index
        # The paragraphs are not siblings, so nth-of-type won't work
        paragraphs = result.query_selector_all("p")

        name = ""
        headline = ""
        current_job = ""

        if len(paragraphs) >= 2:
            # New UI: first paragraph is name (with degree), second is headline
            raw_name = paragraphs[0].inner_text().strip() if paragraphs[0] else ""
            name = clean_name(raw_name)
            headline = paragraphs[1].inner_text().strip() if paragraphs[1] else ""

            # Look for "Current:" paragraph which contains the actual company
            # Skip "Past:" - we only want current employees, not former ones
            # This is typically paragraph 3 or 4, and has a <strong> tag with company name
            for p in paragraphs[2:]:
                p_text = p.inner_text().strip()
                if p_text.startswith("Current:"):
                    current_job = p_text
                    break
                elif p_text.startswith("Past:"):
                    # Found "Past:" but no "Current:" yet - this person used to work there
                    # Don't set current_job, they'll only match if company is in headline
                    logger.debug(f"Found 'Past:' for {name}: {p_text[:60]}...")
                    break
        else:
            # Fallback to old selector-based extraction
            raw_name = extract_text_from_element(result, LinkedInSelectors.PERSON_NAME)
            name = clean_name(raw_name)
            headline = extract_text_from_element(result, LinkedInSelectors.PERSON_HEADLINE)

        if not name:
            return None

        # Filter by company if specified - check both headline AND current job paragraph
        if company_filter:
            company_lower = company_filter.lower()
            headline_lower = headline.lower() if headline else ""
            current_job_lower = current_job.lower() if current_job else ""

            # Company must be in headline OR in current job line
            if company_lower not in headline_lower and company_lower not in current_job_lower:
                logger.info(f"Skipping {name} - company '{company_filter}' not in headline: '{headline}'")
                return None

        # Get profile link and extract public_id
        link = extract_attribute_from_element(result, LinkedInSelectors.PROFILE_LINK, "href")
        public_id = extract_public_id(link)

        if not public_id:
            return None

        return {
            "name": name,
            "headline": headline,
            "linkedin_url": f"https://www.linkedin.com/in/{public_id}",
            "public_id": public_id,
        }

    except Exception as e:
        logger.error(f"Error extracting person from result: {e}")
        return None


def extract_people_from_search_results(
    page,
    company_filter: str = None,
    limit: int = None,
) -> list[dict]:
    """
    Extract all people from the current search results page.

    Args:
        page: Playwright page object
        company_filter: Optional company name to filter by
        limit: Maximum number of people to extract

    Returns:
        List of person dicts
    """
    people = []

    # Find search results using various selectors
    results = []
    for selector in LinkedInSelectors.SEARCH_RESULTS:
        results = page.query_selector_all(selector)
        if results:
            logger.info(f"Found {len(results)} results using selector: {selector}")
            break

    if not results:
        logger.warning("No search results found with known selectors")
        return []

    for result in results:
        if limit and len(people) >= limit:
            break

        person = extract_person_from_search_result(result, company_filter)
        if person:
            people.append(person)
            logger.info(f"Extracted person: {person.get('name')} - {person.get('headline', '')[:50]}")
        else:
            # Debug: log why extraction failed
            paragraphs = result.query_selector_all("p")
            if paragraphs:
                raw_name = paragraphs[0].inner_text().strip() if len(paragraphs) > 0 else "N/A"
                raw_headline = paragraphs[1].inner_text().strip() if len(paragraphs) > 1 else "N/A"
                logger.info(f"Skipped result - name: '{raw_name[:30]}', headline: '{raw_headline[:50]}', filter: '{company_filter}'")

    return people


def extract_connection_from_card(card) -> dict | None:
    """
    Extract connection information from a connection card element.

    Args:
        card: Playwright element representing a connection card

    Returns:
        Dict with name, headline, linkedin_url, public_id, is_connection=True
    """
    try:
        # Get name
        name = extract_text_from_element(card, LinkedInSelectors.CONNECTION_NAME)
        if not name:
            return None

        # Get headline
        headline = extract_text_from_element(card, LinkedInSelectors.CONNECTION_HEADLINE)

        # Get profile link
        link = extract_attribute_from_element(card, LinkedInSelectors.CONNECTION_LINK, "href")
        public_id = extract_public_id(link)

        if not public_id:
            return None

        return {
            "name": name,
            "headline": headline,
            "linkedin_url": f"https://www.linkedin.com/in/{public_id}",
            "public_id": public_id,
            "is_connection": True,
        }

    except Exception as e:
        logger.error(f"Error extracting connection from card: {e}")
        return None
