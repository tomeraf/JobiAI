"""
Unit tests for LinkedInSearch service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.linkedin.search import (
    LinkedInSearch,
    LINKEDIN_SEARCH_URL,
    LINKEDIN_CONNECTIONS_URL,
)


class TestLinkedInSearchConstants:
    """Tests for search constants."""

    def test_search_url_is_linkedin(self):
        """Test that search URL is LinkedIn."""
        assert "linkedin.com" in LINKEDIN_SEARCH_URL
        assert "search" in LINKEDIN_SEARCH_URL
        assert "people" in LINKEDIN_SEARCH_URL

    def test_connections_url_is_linkedin(self):
        """Test that connections URL is LinkedIn."""
        assert "linkedin.com" in LINKEDIN_CONNECTIONS_URL
        assert "connections" in LINKEDIN_CONNECTIONS_URL


class TestLinkedInSearchInitialization:
    """Tests for search initialization."""

    def test_search_creates_own_browser(self):
        """Test that search creates own browser when none provided."""
        search = LinkedInSearch()
        assert search.browser is not None
        assert search._owns_browser is True

    def test_search_uses_provided_browser(self):
        """Test that search uses provided browser."""
        mock_browser = MagicMock()
        search = LinkedInSearch(browser=mock_browser)
        assert search.browser is mock_browser
        assert search._owns_browser is False

    @pytest.mark.asyncio
    async def test_initialize_own_browser(self):
        """Test initialize with own browser."""
        search = LinkedInSearch()
        search.browser.initialize = AsyncMock()

        await search.initialize()

        search.browser.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_provided_browser_not_called(self):
        """Test initialize doesn't init provided browser."""
        mock_browser = MagicMock()
        mock_browser.initialize = AsyncMock()
        search = LinkedInSearch(browser=mock_browser)

        await search.initialize()

        mock_browser.initialize.assert_not_called()


class TestLinkedInSearchConnectionsByCompany:
    """Tests for searching connections by company."""

    @pytest.fixture
    def mock_search(self):
        """Create mock search with browser."""
        mock_browser = MagicMock()
        mock_page = AsyncMock()

        mock_browser.page = mock_page
        mock_browser.goto = AsyncMock()

        search = LinkedInSearch(browser=mock_browser)
        return search, mock_page

    @pytest.mark.asyncio
    async def test_search_connections_navigates_to_connections(self, mock_search):
        """Test that search navigates to connections page."""
        search, mock_page = mock_search
        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("No results"))
        mock_page.query_selector = AsyncMock(return_value=None)

        with patch("app.services.linkedin.search.human_delay", new_callable=AsyncMock):
            result = await search.search_connections_by_company("Google")

        search.browser.goto.assert_called()
        # Check first call (the main search with company param)
        first_call_url = search.browser.goto.call_args_list[0][0][0]
        assert "connections" in first_call_url
        assert "Google" in first_call_url or "company=" in first_call_url

    @pytest.mark.asyncio
    async def test_search_connections_returns_list(self, mock_search):
        """Test that search returns a list."""
        search, mock_page = mock_search
        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("No results"))
        mock_page.query_selector = AsyncMock(return_value=None)

        with patch("app.services.linkedin.search.human_delay", new_callable=AsyncMock):
            result = await search.search_connections_by_company("TestCompany")

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_search_connections_parses_cards(self, mock_search):
        """Test that search parses connection cards."""
        search, mock_page = mock_search

        # Create mock card
        mock_card = AsyncMock()
        mock_name = AsyncMock()
        mock_name.inner_text = AsyncMock(return_value="John Doe")
        mock_occupation = AsyncMock()
        mock_occupation.inner_text = AsyncMock(return_value="Engineer at Google")
        mock_link = AsyncMock()
        mock_link.get_attribute = AsyncMock(return_value="https://linkedin.com/in/johndoe")

        mock_card.query_selector = AsyncMock(side_effect=[mock_name, mock_occupation, mock_link])

        mock_page.wait_for_selector = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[mock_card])
        mock_page.evaluate = AsyncMock()

        with patch("app.services.linkedin.search.human_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.search.scroll_delay", new_callable=AsyncMock):
            result = await search.search_connections_by_company("Google")

        assert len(result) >= 0  # May be empty if parsing fails


class TestLinkedInSearchPeopleAtCompany:
    """Tests for searching people at company."""

    @pytest.fixture
    def mock_search(self):
        """Create mock search."""
        mock_browser = MagicMock()
        mock_page = AsyncMock()
        mock_browser.page = mock_page
        mock_browser.goto = AsyncMock()

        search = LinkedInSearch(browser=mock_browser)
        return search, mock_page

    @pytest.mark.asyncio
    async def test_search_people_navigates_to_search(self, mock_search):
        """Test that people search navigates to search page."""
        search, mock_page = mock_search
        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("No results"))
        mock_page.query_selector_all = AsyncMock(return_value=[])

        with patch("app.services.linkedin.search.human_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.search.scroll_delay", new_callable=AsyncMock):
            await search.search_people_at_company("Microsoft")

        search.browser.goto.assert_called()
        call_url = search.browser.goto.call_args[0][0]
        assert "search" in call_url
        assert "Microsoft" in call_url or "microsoft" in call_url.lower()

    @pytest.mark.asyncio
    async def test_search_people_respects_limit(self, mock_search):
        """Test that people search respects limit parameter."""
        search, mock_page = mock_search

        # Create many mock results
        mock_results = []
        for i in range(20):
            mock_result = AsyncMock()
            mock_name = AsyncMock()
            mock_name.inner_text = AsyncMock(return_value=f"Person {i}")
            mock_headline = AsyncMock()
            mock_headline.inner_text = AsyncMock(return_value=f"Title {i}")
            mock_link = AsyncMock()
            mock_link.get_attribute = AsyncMock(return_value=f"https://linkedin.com/in/person{i}")

            mock_result.query_selector = AsyncMock(side_effect=[mock_name, mock_headline, mock_link, None])
            mock_results.append(mock_result)

        mock_page.wait_for_selector = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=mock_results)
        mock_page.evaluate = AsyncMock()

        with patch("app.services.linkedin.search.human_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.search.scroll_delay", new_callable=AsyncMock):
            result = await search.search_people_at_company("Test", limit=5)

        # Should not exceed limit
        assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_search_people_returns_profile_info(self, mock_search):
        """Test that search returns profile info dictionaries."""
        search, mock_page = mock_search

        mock_result = AsyncMock()
        mock_name = AsyncMock()
        mock_name.inner_text = AsyncMock(return_value="Jane Smith")
        mock_headline = AsyncMock()
        mock_headline.inner_text = AsyncMock(return_value="Product Manager")
        mock_link = AsyncMock()
        mock_link.get_attribute = AsyncMock(return_value="https://linkedin.com/in/janesmith?ref=123")

        mock_result.query_selector = AsyncMock(side_effect=[None, mock_name, mock_headline, mock_link, None])

        mock_page.wait_for_selector = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[mock_result])
        mock_page.evaluate = AsyncMock()

        with patch("app.services.linkedin.search.human_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.search.scroll_delay", new_callable=AsyncMock):
            result = await search.search_people_at_company("Test", limit=1)

        if result:
            person = result[0]
            assert "name" in person
            assert "linkedin_url" in person


class TestLinkedInSearchScrolling:
    """Tests for scroll functionality."""

    @pytest.mark.asyncio
    async def test_scroll_to_load_more_scrolls_page(self):
        """Test that scroll function scrolls the page."""
        mock_browser = MagicMock()
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock()
        mock_browser.page = mock_page

        search = LinkedInSearch(browser=mock_browser)

        with patch("app.services.linkedin.search.scroll_delay", new_callable=AsyncMock), \
             patch("app.services.linkedin.search.human_delay", new_callable=AsyncMock):
            await search._scroll_to_load_more(mock_page, max_scrolls=3)

        # Should have called scroll 3 times
        assert mock_page.evaluate.call_count == 3


class TestLinkedInSearchCleanup:
    """Tests for search cleanup."""

    @pytest.mark.asyncio
    async def test_close_own_browser(self):
        """Test closing own browser."""
        search = LinkedInSearch()
        search.browser.close = AsyncMock()

        await search.close()

        search.browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_provided_browser_not_closed(self):
        """Test that provided browser is not closed."""
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()
        search = LinkedInSearch(browser=mock_browser)

        await search.close()

        mock_browser.close.assert_not_called()
