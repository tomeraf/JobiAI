"""
VIP title detection for LinkedIn contacts.

Filters out important people (CEOs, founders, etc.) who shouldn't be cold-messaged.
"""

# Titles that indicate someone is too important to cold-message
VIP_TITLES = [
    'ceo', 'chief executive',
    'cto', 'chief technology',
    'cfo', 'chief financial',
    'coo', 'chief operating',
    'cmo', 'chief marketing',
    'cpo', 'chief product',
    'founder', 'co-founder', 'cofounder',
    'owner', 'president', 'chairman',
    'managing director', 'general manager',
    'vp ', 'vice president',  # Note: space after 'vp' to avoid matching 'vp of recruiting'
]


def is_vip(headline: str) -> bool:
    """
    Check if a person's headline indicates they're a VIP.

    VIPs (CEOs, founders, etc.) should not be cold-messaged or cold-connected.

    Args:
        headline: The person's LinkedIn headline/title

    Returns:
        True if the person appears to be a VIP
    """
    if not headline:
        return False

    headline_lower = headline.lower()
    return any(title in headline_lower for title in VIP_TITLES)


def filter_non_vips(people: list[dict], headline_key: str = "headline") -> list[dict]:
    """
    Filter a list of people to exclude VIPs.

    Args:
        people: List of person dicts
        headline_key: Key in the dict containing the headline

    Returns:
        List with VIPs removed
    """
    return [p for p in people if not is_vip(p.get(headline_key, ""))]
