"""
Person data extraction from LinkedIn search results.

Centralized logic for extracting name, headline, and profile URL from search result elements.
"""

from app.utils.logger import get_logger
from .selectors import LinkedInSelectors

logger = get_logger(__name__)


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
        company_filter: Optional company name to filter by (must be in headline)

    Returns:
        Dict with name, headline, linkedin_url, public_id, or None if extraction failed
    """
    try:
        # Get name
        name = extract_text_from_element(result, LinkedInSelectors.PERSON_NAME)
        if not name:
            return None

        # Get headline
        headline = extract_text_from_element(result, LinkedInSelectors.PERSON_HEADLINE)

        # Filter by company if specified
        if company_filter and headline:
            if company_filter.lower() not in headline.lower():
                logger.debug(f"Skipping {name} - company '{company_filter}' not in headline: '{headline}'")
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
