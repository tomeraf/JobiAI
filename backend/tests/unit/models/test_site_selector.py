"""
Unit tests for SiteSelector model.
"""
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.site_selector import SiteSelector


class TestSiteSelectorModel:
    """Tests for the SiteSelector model."""

    @pytest.mark.asyncio
    async def test_create_site_selector(self, db_session: AsyncSession):
        """Test creating a new site selector."""
        selector = SiteSelector(
            domain="linkedin.com",
            company_selector=".company-name"
        )
        db_session.add(selector)
        await db_session.flush()
        await db_session.refresh(selector)

        assert selector.id is not None
        assert selector.domain == "linkedin.com"
        assert selector.company_selector == ".company-name"
        assert selector.title_selector is None
        assert selector.created_at is not None
        assert selector.last_used_at is None

    @pytest.mark.asyncio
    async def test_create_site_selector_with_all_fields(self, db_session: AsyncSession):
        """Test creating a site selector with all fields."""
        selector = SiteSelector(
            domain="indeed.com",
            company_selector='[data-testid="company-name"]',
            title_selector='[data-testid="job-title"]',
            example_url="https://indeed.com/job/123",
            example_company="Test Company Inc."
        )
        db_session.add(selector)
        await db_session.flush()
        await db_session.refresh(selector)

        assert selector.domain == "indeed.com"
        assert selector.company_selector == '[data-testid="company-name"]'
        assert selector.title_selector == '[data-testid="job-title"]'
        assert selector.example_url == "https://indeed.com/job/123"
        assert selector.example_company == "Test Company Inc."

    @pytest.mark.asyncio
    async def test_site_selector_unique_domain(self, db_session: AsyncSession):
        """Test that domain must be unique."""
        selector1 = SiteSelector(
            domain="unique-site.com",
            company_selector=".company"
        )
        db_session.add(selector1)
        await db_session.flush()

        selector2 = SiteSelector(
            domain="unique-site.com",  # Same domain
            company_selector=".other-company"
        )
        db_session.add(selector2)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_site_selector_last_used_tracking(self, db_session: AsyncSession):
        """Test updating last_used_at."""
        selector = SiteSelector(
            domain="glassdoor.com",
            company_selector=".employer-name"
        )
        db_session.add(selector)
        await db_session.flush()
        await db_session.refresh(selector)

        assert selector.last_used_at is None

        # Update last used
        selector.last_used_at = datetime.utcnow()
        await db_session.flush()
        await db_session.refresh(selector)

        assert selector.last_used_at is not None

    @pytest.mark.asyncio
    async def test_site_selector_repr(self, db_session: AsyncSession):
        """Test site selector string representation."""
        selector = SiteSelector(
            domain="test-site.com",
            company_selector=".company"
        )
        db_session.add(selector)
        await db_session.flush()
        await db_session.refresh(selector)

        repr_str = repr(selector)
        assert "SiteSelector" in repr_str
        assert "test-site.com" in repr_str

    @pytest.mark.asyncio
    async def test_complex_css_selector(self, db_session: AsyncSession):
        """Test storing complex CSS selectors."""
        complex_selector = 'div[class*="job-details"] > section:nth-child(2) span.company-name a'
        selector = SiteSelector(
            domain="complex-site.com",
            company_selector=complex_selector
        )
        db_session.add(selector)
        await db_session.flush()
        await db_session.refresh(selector)

        assert selector.company_selector == complex_selector

    @pytest.mark.asyncio
    async def test_selector_with_hebrew_example(self, db_session: AsyncSession):
        """Test storing Hebrew example company name."""
        selector = SiteSelector(
            domain="drushim.co.il",
            company_selector=".company-name",
            example_company="חברת הייטק ישראלית"
        )
        db_session.add(selector)
        await db_session.flush()
        await db_session.refresh(selector)

        assert selector.example_company == "חברת הייטק ישראלית"


class TestSiteSelectorQueries:
    """Tests for site selector database queries."""

    @pytest.mark.asyncio
    async def test_query_by_domain(self, db_session: AsyncSession, sample_site_selector: SiteSelector):
        """Test querying selector by domain."""
        result = await db_session.execute(
            select(SiteSelector).where(SiteSelector.domain == sample_site_selector.domain)
        )
        found = result.scalar_one_or_none()

        assert found is not None
        assert found.domain == sample_site_selector.domain

    @pytest.mark.asyncio
    async def test_query_nonexistent_domain(self, db_session: AsyncSession):
        """Test querying for non-existent domain."""
        result = await db_session.execute(
            select(SiteSelector).where(SiteSelector.domain == "nonexistent.com")
        )
        found = result.scalar_one_or_none()

        assert found is None

    @pytest.mark.asyncio
    async def test_query_selectors_ordered_by_last_used(self, db_session: AsyncSession):
        """Test querying selectors ordered by last used."""
        selectors = [
            SiteSelector(domain="site1.com", company_selector=".c1", last_used_at=datetime(2024, 1, 1)),
            SiteSelector(domain="site2.com", company_selector=".c2", last_used_at=datetime(2024, 3, 1)),
            SiteSelector(domain="site3.com", company_selector=".c3", last_used_at=datetime(2024, 2, 1)),
        ]
        db_session.add_all(selectors)
        await db_session.flush()

        result = await db_session.execute(
            select(SiteSelector).order_by(SiteSelector.last_used_at.desc().nulls_last())
        )
        ordered = result.scalars().all()

        # site2.com should be first (most recently used)
        assert ordered[0].domain == "site2.com"

    @pytest.mark.asyncio
    async def test_list_all_domains(self, db_session: AsyncSession):
        """Test listing all registered domains."""
        selectors = [
            SiteSelector(domain="a.com", company_selector=".a"),
            SiteSelector(domain="b.com", company_selector=".b"),
            SiteSelector(domain="c.com", company_selector=".c"),
        ]
        db_session.add_all(selectors)
        await db_session.flush()

        result = await db_session.execute(select(SiteSelector))
        all_selectors = result.scalars().all()

        domains = {s.domain for s in all_selectors}
        assert "a.com" in domains
        assert "b.com" in domains
        assert "c.com" in domains

    @pytest.mark.asyncio
    async def test_update_selector(self, db_session: AsyncSession, sample_site_selector: SiteSelector):
        """Test updating an existing selector."""
        original_selector = sample_site_selector.company_selector
        sample_site_selector.company_selector = ".new-company-selector"
        await db_session.flush()
        await db_session.refresh(sample_site_selector)

        assert sample_site_selector.company_selector == ".new-company-selector"
        assert sample_site_selector.company_selector != original_selector

    @pytest.mark.asyncio
    async def test_delete_selector(self, db_session: AsyncSession):
        """Test deleting a selector."""
        selector = SiteSelector(domain="to-delete.com", company_selector=".delete")
        db_session.add(selector)
        await db_session.flush()

        selector_id = selector.id
        await db_session.delete(selector)
        await db_session.flush()

        result = await db_session.execute(
            select(SiteSelector).where(SiteSelector.id == selector_id)
        )
        found = result.scalar_one_or_none()
        assert found is None
