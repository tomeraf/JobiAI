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
            content_male="Hi {name}, I saw you work at {company}!",
            content_female="Hi {name}, I saw you work at {company}!",
            content_neutral="Hello {name}, I noticed your connection to {company}!"
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
            content_male="Male content",
            content_female="Female content",
            content_neutral="Neutral content",
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
            content_male="היי {name}, ראיתי שאתה עובד ב-{company}!",
            content_female="היי {name}, ראיתי שאת עובדת ב-{company}!",
            content_neutral="שלום {name}, ראיתי את הקשר שלך ל-{company}!"
        )
        db_session.add(template)
        await db_session.flush()
        await db_session.refresh(template)

        assert "שאתה עובד" in template.content_male
        assert "שאת עובדת" in template.content_female

    @pytest.mark.asyncio
    async def test_template_repr(self, db_session: AsyncSession):
        """Test template string representation."""
        template = Template(
            name="Repr Test",
            content_male="male",
            content_female="female",
            content_neutral="neutral",
            is_default=True
        )
        db_session.add(template)
        await db_session.flush()
        await db_session.refresh(template)

        repr_str = repr(template)
        assert "Template" in repr_str
        assert "Repr Test" in repr_str
        assert "True" in repr_str


class TestTemplateGetContentForGender:
    """Tests for get_content_for_gender method."""

    @pytest.mark.asyncio
    async def test_get_content_male(self, sample_template: Template):
        """Test getting male content."""
        content = sample_template.get_content_for_gender("male")
        assert "שאתה עובד" in content

    @pytest.mark.asyncio
    async def test_get_content_female(self, sample_template: Template):
        """Test getting female content."""
        content = sample_template.get_content_for_gender("female")
        assert "שאת עובדת" in content

    @pytest.mark.asyncio
    async def test_get_content_neutral(self, sample_template: Template):
        """Test getting neutral content."""
        content = sample_template.get_content_for_gender("neutral")
        assert "שלום" in content

    @pytest.mark.asyncio
    async def test_get_content_unknown_defaults_to_neutral(self, sample_template: Template):
        """Test that unknown gender returns neutral content."""
        content = sample_template.get_content_for_gender("unknown")
        assert content == sample_template.content_neutral

    @pytest.mark.asyncio
    async def test_get_content_invalid_defaults_to_neutral(self, sample_template: Template):
        """Test that invalid gender returns neutral content."""
        content = sample_template.get_content_for_gender("invalid")
        assert content == sample_template.content_neutral


class TestTemplateFormatMessage:
    """Tests for format_message method."""

    @pytest.mark.asyncio
    async def test_format_message_male(self, sample_template: Template):
        """Test formatting message for male."""
        message = sample_template.format_message(
            gender="male",
            name="דוד",
            company="גוגל"
        )
        assert "דוד" in message
        assert "גוגל" in message
        assert "{name}" not in message
        assert "{company}" not in message

    @pytest.mark.asyncio
    async def test_format_message_female(self, sample_template: Template):
        """Test formatting message for female."""
        message = sample_template.format_message(
            gender="female",
            name="שרה",
            company="מיקרוסופט"
        )
        assert "שרה" in message
        assert "מיקרוסופט" in message
        assert "שאת עובדת" in message

    @pytest.mark.asyncio
    async def test_format_message_neutral(self, sample_template: Template):
        """Test formatting message for neutral gender."""
        message = sample_template.format_message(
            gender="unknown",
            name="טל",
            company="אמזון"
        )
        assert "טל" in message
        assert "אמזון" in message

    @pytest.mark.asyncio
    async def test_format_message_english_names(self, sample_template: Template):
        """Test formatting with English names."""
        message = sample_template.format_message(
            gender="male",
            name="John",
            company="Google"
        )
        assert "John" in message
        assert "Google" in message

    @pytest.mark.asyncio
    async def test_format_message_with_special_characters(self, db_session: AsyncSession):
        """Test formatting with special characters in values."""
        template = Template(
            name="Test",
            content_male="Hello {name} at {company}!",
            content_female="Hello {name} at {company}!",
            content_neutral="Hello {name} at {company}!"
        )
        db_session.add(template)
        await db_session.flush()

        message = template.format_message(
            gender="male",
            name="O'Brien",
            company="AT&T Corp."
        )
        assert "O'Brien" in message
        assert "AT&T Corp." in message


class TestTemplateQueries:
    """Tests for template database queries."""

    @pytest.mark.asyncio
    async def test_query_default_template(self, db_session: AsyncSession, sample_template: Template):
        """Test querying for default template."""
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
            Template(name="T1", content_male="m", content_female="f", content_neutral="n", is_default=False),
            Template(name="T2", content_male="m", content_female="f", content_neutral="n", is_default=True),
            Template(name="T3", content_male="m", content_female="f", content_neutral="n", is_default=False),
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
            Template(name=f"Template {i}", content_male=f"m{i}", content_female=f"f{i}", content_neutral=f"n{i}")
            for i in range(5)
        ]
        db_session.add_all(templates)
        await db_session.flush()

        result = await db_session.execute(select(Template))
        all_templates = result.scalars().all()

        assert len(all_templates) >= 5
