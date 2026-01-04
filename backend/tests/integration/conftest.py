"""
Integration test fixtures for JobiAI.

These fixtures provide more comprehensive test setup than unit test fixtures,
including mocked LinkedIn services and workflow orchestrator components.
"""
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport

from app.database import Base, get_db
from app.main import app
from app.models.job import Job, JobStatus, WorkflowStep
from app.models.contact import Contact
from app.models.template import Template
from app.models.activity import ActivityLog, ActionType
from app.models.site_selector import SiteSelector, SiteType
from app.models.hebrew_name import HebrewName


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


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
# Template Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def default_template(db_session: AsyncSession) -> Template:
    """Create a default Hebrew template for testing."""
    template = Template(
        name="Default Hebrew Template",
        content="היי {name}, ראיתי שאתה עובד ב-{company} וחשבתי ליצור קשר!",
        is_default=True
    )
    db_session.add(template)
    await db_session.flush()
    await db_session.refresh(template)
    return template


@pytest_asyncio.fixture
async def english_template(db_session: AsyncSession) -> Template:
    """Create an English template for testing."""
    template = Template(
        name="English Template",
        content="Hi {name}, I saw you work at {company} and wanted to connect!",
        is_default=False
    )
    db_session.add(template)
    await db_session.flush()
    await db_session.refresh(template)
    return template


# ============================================================================
# Selector Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def greenhouse_selector(db_session: AsyncSession) -> SiteSelector:
    """Create a Greenhouse site selector."""
    selector = SiteSelector(
        domain="greenhouse.io",
        site_type=SiteType.PLATFORM,
        platform_name="Greenhouse",
        url_pattern=r"https?://(?:www\.)?([^.]+)\.greenhouse\.io",
        example_url="https://acme.greenhouse.io/jobs/123",
        example_company="acme"
    )
    db_session.add(selector)
    await db_session.flush()
    await db_session.refresh(selector)
    return selector


@pytest_asyncio.fixture
async def company_site_selector(db_session: AsyncSession) -> SiteSelector:
    """Create a company website selector."""
    selector = SiteSelector(
        domain="techcorp.com",
        site_type=SiteType.COMPANY,
        company_name="TechCorp",
        example_url="https://careers.techcorp.com/jobs/123"
    )
    db_session.add(selector)
    await db_session.flush()
    await db_session.refresh(selector)
    return selector


# ============================================================================
# Hebrew Name Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def hebrew_names(db_session: AsyncSession) -> list[HebrewName]:
    """Create sample Hebrew name translations."""
    names = [
        HebrewName(english_name="david", hebrew_name="דויד"),
        HebrewName(english_name="sarah", hebrew_name="שרה"),
        HebrewName(english_name="michael", hebrew_name="מיכאל"),
    ]
    for name in names:
        db_session.add(name)
    await db_session.flush()
    for name in names:
        await db_session.refresh(name)
    return names


# ============================================================================
# Job Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def pending_job(db_session: AsyncSession) -> Job:
    """Create a pending job."""
    job = Job(
        url="https://acme.greenhouse.io/jobs/12345",
        status=JobStatus.PENDING,
        workflow_step=WorkflowStep.COMPANY_EXTRACTION
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


@pytest_asyncio.fixture
async def job_with_company(db_session: AsyncSession) -> Job:
    """Create a job with company already extracted."""
    job = Job(
        url="https://acme.greenhouse.io/jobs/12345",
        company_name="Acme Corp",
        status=JobStatus.COMPLETED,
        workflow_step=WorkflowStep.COMPANY_EXTRACTION
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


@pytest_asyncio.fixture
async def job_needs_input(db_session: AsyncSession) -> Job:
    """Create a job waiting for user input."""
    job = Job(
        url="https://unknown-site.com/jobs/123",
        status=JobStatus.NEEDS_INPUT,
        workflow_step=WorkflowStep.COMPANY_EXTRACTION
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


@pytest_asyncio.fixture
async def job_waiting_for_reply(db_session: AsyncSession) -> Job:
    """Create a job waiting for message replies."""
    job = Job(
        url="https://acme.greenhouse.io/jobs/12345",
        company_name="Acme Corp",
        status=JobStatus.COMPLETED,
        workflow_step=WorkflowStep.WAITING_FOR_REPLY
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


@pytest_asyncio.fixture
async def job_waiting_for_accept(db_session: AsyncSession) -> Job:
    """Create a job waiting for connection accepts."""
    job = Job(
        url="https://acme.greenhouse.io/jobs/12345",
        company_name="Acme Corp",
        status=JobStatus.COMPLETED,
        workflow_step=WorkflowStep.WAITING_FOR_ACCEPT
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


@pytest_asyncio.fixture
async def job_needs_hebrew_names(db_session: AsyncSession) -> Job:
    """Create a job waiting for Hebrew name translations."""
    job = Job(
        url="https://acme.greenhouse.io/jobs/12345",
        company_name="Acme Corp",
        status=JobStatus.NEEDS_INPUT,
        workflow_step=WorkflowStep.NEEDS_HEBREW_NAMES,
        pending_hebrew_names=["John", "Jane"]
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


# ============================================================================
# Contact Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def messaged_contacts(db_session: AsyncSession, job_waiting_for_reply: Job) -> list[Contact]:
    """Create contacts that have been messaged."""
    contacts = [
        Contact(
            linkedin_url="https://linkedin.com/in/john-doe",
            name="John Doe",
            company="Acme Corp",
            position="Software Engineer",
            is_connection=True,
            message_sent_at=datetime.utcnow(),
            message_content="Hi John!",
            job_id=job_waiting_for_reply.id
        ),
        Contact(
            linkedin_url="https://linkedin.com/in/jane-smith",
            name="Jane Smith",
            company="Acme Corp",
            position="Product Manager",
            is_connection=True,
            message_sent_at=datetime.utcnow(),
            message_content="Hi Jane!",
            job_id=job_waiting_for_reply.id
        ),
    ]
    for contact in contacts:
        db_session.add(contact)
    await db_session.flush()
    for contact in contacts:
        await db_session.refresh(contact)
    return contacts


@pytest_asyncio.fixture
async def connection_requested_contacts(db_session: AsyncSession, job_waiting_for_accept: Job) -> list[Contact]:
    """Create contacts with pending connection requests."""
    contacts = [
        Contact(
            linkedin_url="https://linkedin.com/in/bob-wilson",
            name="Bob Wilson",
            company="Acme Corp",
            position="Engineering Manager",
            is_connection=False,
            connection_requested_at=datetime.utcnow(),
            job_id=job_waiting_for_accept.id
        ),
    ]
    for contact in contacts:
        db_session.add(contact)
    await db_session.flush()
    for contact in contacts:
        await db_session.refresh(contact)
    return contacts


# Note: LinkedIn mock fixtures are defined in test files where needed
# to avoid global patches interfering with tests that need real logic
