"""
Centralized CSS selectors for LinkedIn automation.

All LinkedIn selectors in one place for easy maintenance when LinkedIn changes their UI.
"""


class LinkedInSelectors:
    """All CSS selectors used for LinkedIn automation."""

    # Search input on feed page
    SEARCH_INPUT = [
        "input.search-global-typeahead__input",
        "input[placeholder*='Search']",
        "input[aria-label*='Search']",
        ".search-global-typeahead input",
    ]

    # People tab in search results
    PEOPLE_TAB = [
        "button:has-text('People')",
        "a:has-text('People')",
        "[data-test-search-tab='PEOPLE']",
        ".search-reusables__filter-pill-button:has-text('People')",
        ".artdeco-pill:has-text('People')",
        "button.search-reusables__filter-pill-button:has-text('People')",
        "li button:has-text('People')",
        "nav a:has-text('People')",
        ".search-navigation a:has-text('People')",
    ]

    # Search result containers
    SEARCH_RESULTS = [
        # New LinkedIn UI (2026) - role-based list structure
        "[role='list'] > div:has(a[href*='/in/'])",
        "[role='list'] > div li",
        # Fallback to older selectors
        "li.reusable-search__result-container",
        "div.entity-result",
        "[data-view-name='search-entity-result-universal-template']",
        ".search-results-container li",
    ]

    # Person name in search result
    PERSON_NAME = [
        # New LinkedIn UI (2026) - name is in first paragraph
        "p:first-of-type",
        # Fallback to older selectors
        "span.entity-result__title-text a span[aria-hidden='true']",
        "span.entity-result__title-text span[aria-hidden='true']",
        ".entity-result__title-text",
        "span.t-bold",
        "a span[aria-hidden='true']",
    ]

    # Person headline in search result
    PERSON_HEADLINE = [
        # New LinkedIn UI (2026) - headline is in second paragraph
        "p:nth-of-type(2)",
        # Fallback to older selectors
        "div.entity-result__primary-subtitle",
        ".entity-result__primary-subtitle",
        "div.t-14.t-normal",
        ".t-normal",
    ]

    # Profile link in search result
    PROFILE_LINK = [
        "a.app-aware-link[href*='/in/']",
        "a[href*='/in/']",
    ]

    # Connection degree filters
    @staticmethod
    def degree_filter(degree: str) -> list[str]:
        """Get selectors for a specific connection degree filter."""
        return [
            # New LinkedIn UI (2026) - radio buttons
            f"[role='radio']:has-text('{degree}')",
            f"input[type='checkbox'][name='{degree}']",
            # Fallback to older selectors
            f"button:has-text('{degree}')",
            f"button[aria-label*='{degree}']",
            f".search-reusables__filter-pill-button:has-text('{degree}')",
            f"li button:has-text('{degree}')",
            f".artdeco-pill:has-text('{degree}')",
            f"button.artdeco-pill--choice:has-text('{degree}')",
        ]

    # Active degree filter (for clearing)
    ACTIVE_DEGREE_FILTERS = [
        # New LinkedIn UI (2026) - radio buttons with checked state
        "[role='radio'][aria-checked='true']:has-text('1st')",
        "[role='radio'][aria-checked='true']:has-text('2nd')",
        "[role='radio'][aria-checked='true']:has-text('3rd')",
        "input[type='checkbox']:checked",
        # Fallback to older selectors
        "button.artdeco-pill--selected:has-text('1st')",
        "button.artdeco-pill--selected:has-text('2nd')",
        "button.artdeco-pill--selected:has-text('3rd')",
        "button[aria-pressed='true']:has-text('1st')",
        "button[aria-pressed='true']:has-text('2nd')",
        "button[aria-pressed='true']:has-text('3rd')",
    ]

    # Connections dropdown filter (fallback if direct degree filters don't work)
    CONNECTIONS_DROPDOWN = [
        "[role='radio']:has-text('Connections')",
        "button:has-text('Connections')",
        "button[aria-label*='Connections']",
        ".search-reusables__filter-pill-button:has-text('Connections')",
    ]

    # Show/Apply results button in filter dropdown
    SHOW_RESULTS = [
        "button:has-text('Show')",
        "button:has-text('Apply')",
        "button[aria-label*='Apply']",
    ]

    # Next page button
    NEXT_PAGE = [
        "button[aria-label='Next']",
        "button:has-text('Next')",
        "a[aria-label='Next']",
        "[aria-label='Next']",
    ]

    # Message button on search results
    # NOTE: Similar to Connect, LinkedIn may use links or buttons
    MESSAGE_BUTTON = [
        # New LinkedIn UI (2026) - Message might be a link now
        "a[href*='/messaging/']:has-text('Message')",
        "a:has-text('Message')",
        # Button-based selectors
        "button:has-text('Message')",
        "button[aria-label*='Message']",
        "button[aria-label*='message']",
        # Generic fallbacks
        "[role='button']:has-text('Message')",
    ]

    # Connect button on search results
    # NOTE: LinkedIn changed to links in 2026 - "Invite X to connect" links
    CONNECT_BUTTON = [
        # New LinkedIn UI (2026) - Connect is now a link, not a button
        "a[href*='/preload/search-custom-invite/']",
        "a:has-text('Invite'):has-text('to connect')",
        "link:has-text('Connect')",
        # Fallback to older button selectors
        "button:has-text('Connect')",
        "button[aria-label*='connect']",
    ]

    # Send connection request buttons
    SEND_CONNECTION = [
        "button[aria-label='Send without a note']",
        "button:has-text('Send without a note')",
        "button[aria-label='Send now']",
        "button:has-text('Send')",
    ]

    # Message input in chat modal
    MESSAGE_INPUT = [
        "div.msg-form__contenteditable",
        "[contenteditable='true']",
        "div[role='textbox']",
        ".msg-form__msg-content-container div[contenteditable]",
    ]

    # Send message button
    SEND_MESSAGE = [
        "button.msg-form__send-button",
        "button[type='submit']",
        "button:has-text('Send')",
        "button[aria-label='Send']",
    ]

    # Close/Dismiss buttons
    CLOSE_MODAL = [
        "button[aria-label='Dismiss']",
        "button[aria-label='Close']",
    ]

    # Chat modal/overlay detection
    CHAT_MODAL = [
        "[role='dialog']",
        ".msg-overlay-conversation-bubble",
    ]

    # Chat close buttons
    CHAT_CLOSE = [
        ".msg-overlay-conversation-bubble button[aria-label*='Close']",
        ".msg-overlay-bubble-header button[aria-label*='Close']",
        "[role='dialog'] button[aria-label*='Close']",
    ]

    # Messaging panel (bottom right floating)
    MESSAGING_PANEL_OPEN = [
        ".msg-overlay-list-bubble--is-open",
        ".msg-overlay-list-bubble__conversations-container",
        ".msg-conversations-container",
        ".msg-overlay-list-bubble input[placeholder*='Search']",
        ".msg-search-form input",
    ]

    MESSAGING_BUTTON = [
        ".msg-overlay-list-bubble__header",
        ".msg-overlay-list-bubble__default-header",
        ".msg-overlay-bubble-header",
        "button.msg-overlay-bubble-header__button",
        ".msg-overlay-list-bubble",
        "[data-control-name='overlay.open_messaging_overlay']",
        "button[aria-label='Open messaging overlay']",
        ".msg-overlay-list-bubble-search__search-trigger",
    ]

    MESSAGING_MINIMIZED = [
        ".msg-overlay-list-bubble--is-minimized",
        ".msg-overlay__bubble-minimized",
    ]

    # Messaging search input
    MESSAGING_SEARCH = [
        ".msg-overlay-list-bubble input[placeholder*='Search']",
        ".msg-overlay-list-bubble input[type='search']",
        ".msg-overlay-list-bubble input",
        ".msg-overlay-container input[placeholder*='Search']",
        ".msg-search-form input",
        "input[placeholder*='Search messages']",
        ".msg-overlay-list-bubble__search-container input",
        ".msg-overlay-list-bubble-search__search-typeahead-input",
        ".msg-overlay-list-bubble input[aria-label*='Search']",
    ]

    # Conversation bubble after clicking on a conversation
    CONVERSATION_BUBBLE = [
        ".msg-overlay-conversation-bubble",
        ".msg-convo-wrapper",
        ".msg-s-message-list",
        ".msg-overlay-conversation-bubble--is-active",
    ]

    # Connections page
    CONNECTION_CARDS = [
        "li.mn-connection-card",
        "div.mn-connection-card",
        "[data-view-name='connections-list-item']",
        ".scaffold-finite-scroll__content > li",
    ]

    CONNECTION_NAME = [
        "span.mn-connection-card__name",
        ".entity-result__title-text",
        "a span[aria-hidden='true']",
        "span.t-bold",
    ]

    CONNECTION_HEADLINE = [
        "span.mn-connection-card__occupation",
        ".entity-result__primary-subtitle",
        ".t-normal",
    ]

    CONNECTION_LINK = [
        "a.mn-connection-card__link",
        "a[href*='/in/']",
    ]

    # Nav bar profile image
    NAV_PROFILE_PHOTO = "img.global-nav__me-photo"


# Convenience function to get conversation selectors with a name
def conversation_selectors(name: str) -> list[str]:
    """Get selectors for finding a conversation by person name."""
    return [
        f".msg-overlay-list-bubble li:has-text('{name}')",
        f".msg-conversation-listitem:has-text('{name}')",
        f".msg-conversations-container__convo-item:has-text('{name}')",
        f".msg-overlay-list-bubble__convo-card:has-text('{name}')",
    ]
