"""
Pytest configuration and fixtures for JobiAI tests.
"""
import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

# Import app components
from app.database import Base, get_db
from app.main import app
from app.models.job import Job, JobStatus
from app.models.contact import Contact, Gender
from app.models.template import Template
from app.models.activity import ActivityLog, ActionType
from app.models.site_selector import SiteSelector


# Test database URL (in-memory SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# Event loop is managed by pytest-asyncio with asyncio_mode=auto


@pytest_asyncio.fixture
async def async_engine():
    """Create async test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(async_engine, db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ============================================================================
# Model Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def sample_job(db_session: AsyncSession) -> Job:
    """Create a sample job for testing."""
    job = Job(
        url="https://example.com/jobs/123",
        company_name="Test Company",
        job_title="Software Engineer",
        status=JobStatus.PENDING
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


@pytest_asyncio.fixture
async def sample_contact(db_session: AsyncSession, sample_job: Job) -> Contact:
    """Create a sample contact for testing."""
    contact = Contact(
        linkedin_url="https://linkedin.com/in/testuser",
        name="Test User",
        company="Test Company",
        position="Developer",
        gender=Gender.MALE,
        is_connection=True,
        job_id=sample_job.id
    )
    db_session.add(contact)
    await db_session.flush()
    await db_session.refresh(contact)
    return contact


@pytest_asyncio.fixture
async def sample_template(db_session: AsyncSession) -> Template:
    """Create a sample template for testing."""
    template = Template(
        name="Test Template",
        content_male="היי {name}, ראיתי שאתה עובד ב-{company}!",
        content_female="היי {name}, ראיתי שאת עובדת ב-{company}!",
        content_neutral="שלום {name}, ראיתי את הקשר שלך ל-{company}!",
        is_default=True
    )
    db_session.add(template)
    await db_session.flush()
    await db_session.refresh(template)
    return template


@pytest_asyncio.fixture
async def sample_activity_log(db_session: AsyncSession, sample_job: Job) -> ActivityLog:
    """Create a sample activity log for testing."""
    log = ActivityLog(
        action_type=ActionType.JOB_SUBMITTED,
        description="Job submitted for processing",
        details={"url": "https://example.com/jobs/123"},
        job_id=sample_job.id
    )
    db_session.add(log)
    await db_session.flush()
    await db_session.refresh(log)
    return log


@pytest_asyncio.fixture
async def sample_site_selector(db_session: AsyncSession) -> SiteSelector:
    """Create a sample site selector for testing."""
    selector = SiteSelector(
        domain="example.com",
        company_selector=".company-name",
        title_selector=".job-title",
        example_url="https://example.com/jobs/123",
        example_company="Test Company"
    )
    db_session.add(selector)
    await db_session.flush()
    await db_session.refresh(selector)
    return selector


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_playwright():
    """Mock playwright for browser tests."""
    with patch("app.services.linkedin.browser.async_playwright") as mock:
        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw.start = AsyncMock(return_value=mock_pw)
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.storage_state = AsyncMock()

        mock_page.goto = AsyncMock()
        mock_page.url = "https://www.linkedin.com/feed/"
        mock_page.wait_for_selector = AsyncMock()
        mock_page.query_selector = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[])
        mock_page.screenshot = AsyncMock()
        mock_page.close = AsyncMock()
        mock_page.evaluate = AsyncMock()

        mock.return_value.__aenter__ = AsyncMock(return_value=mock_pw)
        mock.return_value.__aexit__ = AsyncMock()

        yield {
            "playwright": mock,
            "pw_instance": mock_pw,
            "browser": mock_browser,
            "context": mock_context,
            "page": mock_page,
        }


@pytest.fixture
def mock_stealth():
    """Mock playwright-stealth."""
    with patch("app.services.linkedin.browser.stealth_async") as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_delays():
    """Mock delay functions to speed up tests."""
    with patch("app.utils.delays.human_delay", new_callable=AsyncMock) as mock_human, \
         patch("app.utils.delays.typing_delay", new_callable=AsyncMock) as mock_typing, \
         patch("app.utils.delays.scroll_delay", new_callable=AsyncMock) as mock_scroll, \
         patch("app.utils.delays.page_load_delay", new_callable=AsyncMock) as mock_page, \
         patch("app.utils.delays.action_delay", new_callable=AsyncMock) as mock_action:
        yield {
            "human_delay": mock_human,
            "typing_delay": mock_typing,
            "scroll_delay": mock_scroll,
            "page_load_delay": mock_page,
            "action_delay": mock_action,
        }
