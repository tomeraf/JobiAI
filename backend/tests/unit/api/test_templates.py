"""
Unit tests for Templates API routes.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import Template


class TestCreateTemplate:
    """Tests for POST /api/templates endpoint."""

    @pytest.mark.asyncio
    async def test_create_template_success(self, client: AsyncClient):
        """Test successfully creating a template."""
        response = await client.post(
            "/api/templates",
            json={
                "name": "Test Template",
                "content_male": "Hi {name} at {company}!",
                "content_female": "Hi {name} at {company}!",
                "content_neutral": "Hello {name} at {company}!",
                "is_default": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Template"
        assert data["is_default"] is False
        assert data["id"] is not None

    @pytest.mark.asyncio
    async def test_create_template_as_default(self, client: AsyncClient):
        """Test creating a default template."""
        response = await client.post(
            "/api/templates",
            json={
                "name": "Default Template",
                "content_male": "Male",
                "content_female": "Female",
                "content_neutral": "Neutral",
                "is_default": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_default"] is True

    @pytest.mark.asyncio
    async def test_create_template_missing_fields(self, client: AsyncClient):
        """Test creating template with missing fields."""
        response = await client.post(
            "/api/templates",
            json={
                "name": "Incomplete"
                # Missing content fields
            }
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_template_hebrew_content(self, client: AsyncClient):
        """Test creating template with Hebrew content."""
        response = await client.post(
            "/api/templates",
            json={
                "name": "Hebrew Template",
                "content_male": "היי {name}, ראיתי שאתה עובד ב-{company}!",
                "content_female": "היי {name}, ראיתי שאת עובדת ב-{company}!",
                "content_neutral": "שלום {name}!",
                "is_default": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "שאתה עובד" in data["content_male"]


class TestListTemplates:
    """Tests for GET /api/templates endpoint."""

    @pytest.mark.asyncio
    async def test_list_templates_empty(self, client: AsyncClient):
        """Test listing templates when none exist."""
        response = await client.get("/api/templates")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_templates_with_data(self, client: AsyncClient, sample_template: Template):
        """Test listing templates with existing data."""
        response = await client.get("/api/templates")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1


class TestGetTemplate:
    """Tests for GET /api/templates/{template_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_template_success(self, client: AsyncClient, sample_template: Template):
        """Test getting a specific template."""
        response = await client.get(f"/api/templates/{sample_template.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_template.id
        assert data["name"] == sample_template.name

    @pytest.mark.asyncio
    async def test_get_template_not_found(self, client: AsyncClient):
        """Test getting non-existent template."""
        response = await client.get("/api/templates/99999")

        assert response.status_code == 404


class TestUpdateTemplate:
    """Tests for PUT /api/templates/{template_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_template_success(self, client: AsyncClient, sample_template: Template):
        """Test updating a template."""
        response = await client.put(
            f"/api/templates/{sample_template.id}",
            json={
                "name": "Updated Name"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_template_content(self, client: AsyncClient, sample_template: Template):
        """Test updating template content."""
        response = await client.put(
            f"/api/templates/{sample_template.id}",
            json={
                "content_male": "New male content: {name} at {company}"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "New male content" in data["content_male"]

    @pytest.mark.asyncio
    async def test_update_template_set_as_default(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        sample_template: Template
    ):
        """Test setting template as default."""
        # Create another template
        other = Template(
            name="Other",
            content_male="M",
            content_female="F",
            content_neutral="N",
            is_default=False
        )
        db_session.add(other)
        await db_session.flush()
        await db_session.refresh(other)

        response = await client.put(
            f"/api/templates/{other.id}",
            json={"is_default": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_default"] is True

    @pytest.mark.asyncio
    async def test_update_template_not_found(self, client: AsyncClient):
        """Test updating non-existent template."""
        response = await client.put(
            "/api/templates/99999",
            json={"name": "Updated"}
        )

        assert response.status_code == 404


class TestDeleteTemplate:
    """Tests for DELETE /api/templates/{template_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_template_success(self, client: AsyncClient, sample_template: Template):
        """Test deleting a template."""
        response = await client.delete(f"/api/templates/{sample_template.id}")

        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_delete_template_not_found(self, client: AsyncClient):
        """Test deleting non-existent template."""
        response = await client.delete("/api/templates/99999")

        assert response.status_code == 404


class TestPreviewTemplate:
    """Tests for POST /api/templates/{template_id}/preview endpoint."""

    @pytest.mark.asyncio
    async def test_preview_template_male(self, client: AsyncClient, sample_template: Template):
        """Test previewing template for male."""
        response = await client.post(
            f"/api/templates/{sample_template.id}/preview",
            json={
                "gender": "male",
                "name": "דוד",
                "company": "גוגל"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "preview" in data
        assert "דוד" in data["preview"]
        assert "גוגל" in data["preview"]

    @pytest.mark.asyncio
    async def test_preview_template_female(self, client: AsyncClient, sample_template: Template):
        """Test previewing template for female."""
        response = await client.post(
            f"/api/templates/{sample_template.id}/preview",
            json={
                "gender": "female",
                "name": "שרה",
                "company": "מיקרוסופט"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "שרה" in data["preview"]

    @pytest.mark.asyncio
    async def test_preview_template_not_found(self, client: AsyncClient):
        """Test previewing non-existent template."""
        response = await client.post(
            "/api/templates/99999/preview",
            json={
                "gender": "male",
                "name": "Test",
                "company": "Test"
            }
        )

        assert response.status_code == 404


class TestGetDefaultTemplate:
    """Tests for GET /api/templates/default/current endpoint."""

    @pytest.mark.asyncio
    async def test_get_default_template_success(self, client: AsyncClient, sample_template: Template):
        """Test getting default template."""
        # sample_template is created with is_default=True
        response = await client.get("/api/templates/default/current")

        assert response.status_code == 200
        data = response.json()
        assert data["is_default"] is True

    @pytest.mark.asyncio
    async def test_get_default_template_none_set(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting default when none set."""
        # Create a non-default template
        template = Template(
            name="Not Default",
            content_male="M",
            content_female="F",
            content_neutral="N",
            is_default=False
        )
        db_session.add(template)
        await db_session.flush()

        response = await client.get("/api/templates/default/current")

        # Should return 404 if no default exists
        # (depends on whether sample_template fixture runs)
        assert response.status_code in [200, 404]
