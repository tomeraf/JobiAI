"""
Unit tests for Template model.
"""
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.template import Template


class TestTemplateModel:
    """Tests for the Template model."""

    @pytest.mark.asyncio
    async def test_create_template(self, db_session: AsyncSession):
        """Test creating a new template."""
        template = Template(
            name="Introduction",
            content="Hi {name}, I saw you work at {company}!"
        )
        db_session.add(template)
        await db_session.flush()
        await db_session.refresh(template)

        assert template.id is not None
        assert template.name == "Introduction"
        assert template.is_default is False
        assert template.created_at is not None
        assert template.updated_at is not None

    @pytest.mark.asyncio
    async def test_template_default_flag(self, db_session: AsyncSession):
        """Test template default flag."""
        template = Template(
            name="Default Template",
            content="Hello {name}!",
            is_default=True
        )
        db_session.add(template)
        await db_session.flush()
        await db_session.refresh(template)

        assert template.is_default is True

    @pytest.mark.asyncio
    async def test_template_hebrew_content(self, db_session: AsyncSession):
        """Test template with Hebrew content."""
        template = Template(
            name="Hebrew Template",
            content="היי {שם}, ראיתי שאתה עובד ב-{חברה}!"
        )
        db_session.add(template)
        await db_session.flush()
        await db_session.refresh(template)

        assert "שאתה עובד" in template.content

    @pytest.mark.asyncio
    async def test_template_repr(self, db_session: AsyncSession):
        """Test template string representation."""
        template = Template(
            name="Repr Test",
            content="test content",
            is_default=True
        )
        db_session.add(template)
        await db_session.flush()
        await db_session.refresh(template)

        repr_str = repr(template)
        assert "Template" in repr_str
        assert "Repr Test" in repr_str
        assert "True" in repr_str


class TestTemplateFormatMessage:
    """Tests for format_message method."""

    @pytest.mark.asyncio
    async def test_format_message_english(self, db_session: AsyncSession):
        """Test formatting message with English placeholders."""
        template = Template(
            name="English",
            content="Hi {name}, I saw you work at {company}!"
        )
        db_session.add(template)
        await db_session.flush()

        message = template.format_message(name="John", company="Google")
        assert "John" in message
        assert "Google" in message
        assert "{name}" not in message
        assert "{company}" not in message

    @pytest.mark.asyncio
    async def test_format_message_hebrew(self, db_session: AsyncSession):
        """Test formatting message with Hebrew placeholders."""
        template = Template(
            name="Hebrew",
            content="היי {שם}, ראיתי שאתה עובד ב-{חברה}!"
        )
        db_session.add(template)
        await db_session.flush()

        message = template.format_message(name="דוד", company="גוגל")
        assert "דוד" in message
        assert "גוגל" in message
        assert "{שם}" not in message
        assert "{חברה}" not in message

    @pytest.mark.asyncio
    async def test_format_message_with_special_characters(self, db_session: AsyncSession):
        """Test formatting with special characters in values."""
        template = Template(
            name="Test",
            content="Hello {name} at {company}!"
        )
        db_session.add(template)
        await db_session.flush()

        message = template.format_message(name="O'Brien", company="AT&T Corp.")
        assert "O'Brien" in message
        assert "AT&T Corp." in message


class TestTemplateQueries:
    """Tests for template database queries."""

    @pytest.mark.asyncio
    async def test_query_default_template(self, db_session: AsyncSession):
        """Test querying for default template."""
        template = Template(
            name="Default",
            content="default content",
            is_default=True
        )
        db_session.add(template)
        await db_session.flush()

        result = await db_session.execute(
            select(Template).where(Template.is_default == True)
        )
        default_template = result.scalar_one_or_none()

        assert default_template is not None
        assert default_template.is_default is True

    @pytest.mark.asyncio
    async def test_query_templates_ordered_by_default(self, db_session: AsyncSession):
        """Test querying templates ordered by default status."""
        templates = [
            Template(name="T1", content="c1", is_default=False),
            Template(name="T2", content="c2", is_default=True),
            Template(name="T3", content="c3", is_default=False),
        ]
        db_session.add_all(templates)
        await db_session.flush()

        result = await db_session.execute(
            select(Template).order_by(Template.is_default.desc())
        )
        ordered = result.scalars().all()

        assert ordered[0].is_default is True
        assert ordered[0].name == "T2"

    @pytest.mark.asyncio
    async def test_multiple_templates(self, db_session: AsyncSession):
        """Test creating and querying multiple templates."""
        templates = [
            Template(name=f"Template {i}", content=f"content {i}")
            for i in range(5)
        ]
        db_session.add_all(templates)
        await db_session.flush()

        result = await db_session.execute(select(Template))
        all_templates = result.scalars().all()

        assert len(all_templates) >= 5
