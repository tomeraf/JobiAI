"""
Unit tests for database configuration.
"""
import pytest
from unittest.mock import patch, AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.database import Base, get_db


class TestDatabaseBase:
    """Tests for database Base class."""

    def test_base_is_declarative(self):
        """Test that Base is a declarative base."""
        assert issubclass(Base, DeclarativeBase)

    def test_base_has_metadata(self):
        """Test that Base has metadata attribute."""
        assert hasattr(Base, "metadata")

    def test_base_metadata_has_tables(self):
        """Test that metadata knows about registered tables."""
        # After importing models, metadata should have tables
        from app.models import Job, Contact, Template, ActivityLog, SiteSelector

        table_names = Base.metadata.tables.keys()
        assert "jobs" in table_names
        assert "contacts" in table_names
        assert "templates" in table_names
        assert "activity_logs" in table_names
        assert "site_selectors" in table_names


class TestGetDb:
    """Tests for get_db dependency function."""

    @pytest.mark.asyncio
    async def test_get_db_returns_session(self, db_session: AsyncSession):
        """Test that get_db yields a session."""
        # Using the fixture which overrides get_db
        assert isinstance(db_session, AsyncSession)

    @pytest.mark.asyncio
    async def test_get_db_is_async_generator(self):
        """Test that get_db is an async generator."""
        import inspect
        assert inspect.isasyncgenfunction(get_db)


class TestDatabaseModels:
    """Tests for database model registration."""

    def test_job_model_registered(self):
        """Test that Job model is registered with Base."""
        from app.models.job import Job
        assert Job.__tablename__ == "jobs"
        assert Job.__table__.name == "jobs"

    def test_contact_model_registered(self):
        """Test that Contact model is registered with Base."""
        from app.models.contact import Contact
        assert Contact.__tablename__ == "contacts"

    def test_template_model_registered(self):
        """Test that Template model is registered with Base."""
        from app.models.template import Template
        assert Template.__tablename__ == "templates"

    def test_activity_log_model_registered(self):
        """Test that ActivityLog model is registered with Base."""
        from app.models.activity import ActivityLog
        assert ActivityLog.__tablename__ == "activity_logs"

    def test_site_selector_model_registered(self):
        """Test that SiteSelector model is registered with Base."""
        from app.models.site_selector import SiteSelector
        assert SiteSelector.__tablename__ == "site_selectors"


class TestDatabaseRelationships:
    """Tests for database relationship definitions."""

    def test_job_has_contacts_relationship(self):
        """Test Job has contacts relationship."""
        from app.models.job import Job
        assert hasattr(Job, "contacts")

    def test_job_has_activity_logs_relationship(self):
        """Test Job has activity_logs relationship."""
        from app.models.job import Job
        assert hasattr(Job, "activity_logs")

    def test_contact_has_job_relationship(self):
        """Test Contact has job relationship."""
        from app.models.contact import Contact
        assert hasattr(Contact, "job")

    def test_activity_log_has_job_relationship(self):
        """Test ActivityLog has job relationship."""
        from app.models.activity import ActivityLog
        assert hasattr(ActivityLog, "job")


class TestDatabaseSession:
    """Tests for database session behavior."""

    @pytest.mark.asyncio
    async def test_session_can_add_objects(self, db_session: AsyncSession):
        """Test that session can add objects."""
        from app.models.job import Job

        job = Job(url="https://test.com/job")
        db_session.add(job)
        await db_session.flush()

        assert job.id is not None

    @pytest.mark.asyncio
    async def test_session_can_query(self, db_session: AsyncSession):
        """Test that session can execute queries."""
        from sqlalchemy import select, text

        result = await db_session.execute(text("SELECT 1"))
        row = result.fetchone()
        assert row[0] == 1

    @pytest.mark.asyncio
    async def test_session_rollback_on_error(self, db_session: AsyncSession):
        """Test that session supports rollback."""
        from app.models.job import Job

        job = Job(url="https://test.com/rollback")
        db_session.add(job)
        await db_session.flush()

        job_id = job.id

        # Rollback
        await db_session.rollback()

        # Job should no longer be in session
        from sqlalchemy import select
        result = await db_session.execute(select(Job).where(Job.id == job_id))
        assert result.scalar_one_or_none() is None


class TestDatabaseTableStructure:
    """Tests for table structure definitions."""

    def test_jobs_table_columns(self):
        """Test jobs table has expected columns."""
        from app.models.job import Job

        columns = {c.name for c in Job.__table__.columns}
        expected = {"id", "url", "company_name", "job_title", "status", "error_message", "created_at", "processed_at"}
        assert expected.issubset(columns)

    def test_contacts_table_columns(self):
        """Test contacts table has expected columns."""
        from app.models.contact import Contact

        columns = {c.name for c in Contact.__table__.columns}
        expected = {"id", "linkedin_url", "name", "company", "gender", "is_connection", "job_id"}
        assert expected.issubset(columns)

    def test_templates_table_columns(self):
        """Test templates table has expected columns."""
        from app.models.template import Template

        columns = {c.name for c in Template.__table__.columns}
        expected = {"id", "name", "content_male", "content_female", "content_neutral", "is_default"}
        assert expected.issubset(columns)

    def test_activity_logs_table_columns(self):
        """Test activity_logs table has expected columns."""
        from app.models.activity import ActivityLog

        columns = {c.name for c in ActivityLog.__table__.columns}
        expected = {"id", "action_type", "description", "details", "job_id", "created_at"}
        assert expected.issubset(columns)

    def test_site_selectors_table_columns(self):
        """Test site_selectors table has expected columns."""
        from app.models.site_selector import SiteSelector

        columns = {c.name for c in SiteSelector.__table__.columns}
        expected = {"id", "domain", "company_selector", "title_selector", "created_at"}
        assert expected.issubset(columns)
