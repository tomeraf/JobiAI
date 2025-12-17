"""
Unit tests for Selectors API routes.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site_selector import SiteSelector
from app.models.activity import ActivityLog, ActionType


class TestCreateSelector:
    """Tests for POST /api/selectors endpoint."""

    @pytest.mark.asyncio
    async def test_create_selector_success(self, client: AsyncClient):
        """Test successfully creating a selector."""
        response = await client.post(
            "/api/selectors",
            json={
                "domain": "newsite.com",
                "company_selector": ".company-name",
                "title_selector": ".job-title"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == "newsite.com"
        assert data["company_selector"] == ".company-name"
        assert data["id"] is not None

    @pytest.mark.asyncio
    async def test_create_selector_with_example(self, client: AsyncClient):
        """Test creating selector with example data."""
        response = await client.post(
            "/api/selectors",
            json={
                "domain": "example-job-site.com",
                "company_selector": "[data-company]",
                "example_url": "https://example-job-site.com/job/123",
                "example_company": "Example Corp"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["example_url"] == "https://example-job-site.com/job/123"
        assert data["example_company"] == "Example Corp"

    @pytest.mark.asyncio
    async def test_create_selector_logs_activity(self, client: AsyncClient, db_session: AsyncSession):
        """Test that creating selector logs activity."""
        response = await client.post(
            "/api/selectors",
            json={
                "domain": "logged-site.com",
                "company_selector": ".company"
            }
        )

        assert response.status_code == 200

        # Check activity was logged
        from sqlalchemy import select
        result = await db_session.execute(
            select(ActivityLog).where(ActivityLog.action_type == ActionType.SELECTOR_LEARNED)
        )
        logs = result.scalars().all()
        assert len(logs) >= 1

    @pytest.mark.asyncio
    async def test_create_selector_duplicate_domain(
        self,
        client: AsyncClient,
        sample_site_selector: SiteSelector
    ):
        """Test creating selector for existing domain fails."""
        response = await client.post(
            "/api/selectors",
            json={
                "domain": sample_site_selector.domain,
                "company_selector": ".other-selector"
            }
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_selector_missing_fields(self, client: AsyncClient):
        """Test creating selector with missing fields."""
        response = await client.post(
            "/api/selectors",
            json={
                "domain": "incomplete.com"
                # Missing company_selector
            }
        )

        assert response.status_code == 422


class TestListSelectors:
    """Tests for GET /api/selectors endpoint."""

    @pytest.mark.asyncio
    async def test_list_selectors_empty(self, client: AsyncClient):
        """Test listing selectors when none exist."""
        response = await client.get("/api/selectors")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_selectors_with_data(self, client: AsyncClient, sample_site_selector: SiteSelector):
        """Test listing selectors with existing data."""
        response = await client.get("/api/selectors")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1


class TestGetSelectorByDomain:
    """Tests for GET /api/selectors/domain/{domain} endpoint."""

    @pytest.mark.asyncio
    async def test_get_selector_by_domain_success(
        self,
        client: AsyncClient,
        sample_site_selector: SiteSelector
    ):
        """Test getting selector by domain."""
        response = await client.get(f"/api/selectors/domain/{sample_site_selector.domain}")

        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == sample_site_selector.domain

    @pytest.mark.asyncio
    async def test_get_selector_by_domain_not_found(self, client: AsyncClient):
        """Test getting selector for unknown domain."""
        response = await client.get("/api/selectors/domain/unknown-domain.com")

        assert response.status_code == 404


class TestGetSelector:
    """Tests for GET /api/selectors/{selector_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_selector_success(self, client: AsyncClient, sample_site_selector: SiteSelector):
        """Test getting selector by ID."""
        response = await client.get(f"/api/selectors/{sample_site_selector.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_site_selector.id

    @pytest.mark.asyncio
    async def test_get_selector_not_found(self, client: AsyncClient):
        """Test getting non-existent selector."""
        response = await client.get("/api/selectors/99999")

        assert response.status_code == 404


class TestUpdateSelector:
    """Tests for PUT /api/selectors/{selector_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_selector_success(
        self,
        client: AsyncClient,
        sample_site_selector: SiteSelector
    ):
        """Test updating a selector."""
        response = await client.put(
            f"/api/selectors/{sample_site_selector.id}",
            json={
                "company_selector": ".updated-selector"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["company_selector"] == ".updated-selector"

    @pytest.mark.asyncio
    async def test_update_selector_title(
        self,
        client: AsyncClient,
        sample_site_selector: SiteSelector
    ):
        """Test updating selector title selector."""
        response = await client.put(
            f"/api/selectors/{sample_site_selector.id}",
            json={
                "title_selector": ".new-title-selector"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title_selector"] == ".new-title-selector"

    @pytest.mark.asyncio
    async def test_update_selector_not_found(self, client: AsyncClient):
        """Test updating non-existent selector."""
        response = await client.put(
            "/api/selectors/99999",
            json={"company_selector": ".test"}
        )

        assert response.status_code == 404


class TestDeleteSelector:
    """Tests for DELETE /api/selectors/{selector_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_selector_success(
        self,
        client: AsyncClient,
        sample_site_selector: SiteSelector
    ):
        """Test deleting a selector."""
        response = await client.delete(f"/api/selectors/{sample_site_selector.id}")

        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_delete_selector_not_found(self, client: AsyncClient):
        """Test deleting non-existent selector."""
        response = await client.delete("/api/selectors/99999")

        assert response.status_code == 404


class TestCheckDomain:
    """Tests for POST /api/selectors/check endpoint."""

    @pytest.mark.asyncio
    async def test_check_domain_has_selector(
        self,
        client: AsyncClient,
        sample_site_selector: SiteSelector
    ):
        """Test checking domain that has selector."""
        response = await client.post(
            "/api/selectors/check",
            params={"url": f"https://{sample_site_selector.domain}/job/123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_selector"] is True
        assert data["selector"] is not None

    @pytest.mark.asyncio
    async def test_check_domain_no_selector(self, client: AsyncClient):
        """Test checking domain without selector."""
        response = await client.post(
            "/api/selectors/check",
            params={"url": "https://unknown-site.com/job/123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_selector"] is False
        assert data["selector"] is None

    @pytest.mark.asyncio
    async def test_check_domain_strips_www(self, client: AsyncClient, db_session: AsyncSession):
        """Test that www is stripped from domain."""
        # Create selector without www
        selector = SiteSelector(domain="test-site.com", company_selector=".company")
        db_session.add(selector)
        await db_session.flush()

        response = await client.post(
            "/api/selectors/check",
            params={"url": "https://www.test-site.com/job"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == "test-site.com"

    @pytest.mark.asyncio
    async def test_check_domain_invalid_url(self, client: AsyncClient):
        """Test checking invalid URL returns empty domain."""
        response = await client.post(
            "/api/selectors/check",
            params={"url": "not a valid url"}
        )
        # URL without scheme parses with empty netloc, returns 200 with empty domain
        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == ""
        assert data["has_selector"] is False
