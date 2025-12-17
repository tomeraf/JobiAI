"""
Unit tests for job processor service.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.job_processor import JobProcessor
from app.models.job import Job, JobStatus
from app.models.site_selector import SiteSelector, SiteType
from app.models.activity import ActivityLog, ActionType


class TestJobProcessor:
    """Tests for JobProcessor class."""

    @pytest.mark.asyncio
    async def test_process_job_with_known_company_site(self, db_session: AsyncSession):
        """Test processing job with a known company site in database."""
        # Create a selector for a company website
        selector = SiteSelector(
            domain="testcompany.com",
            site_type=SiteType.COMPANY,
            company_name="Test Company Inc",
        )
        db_session.add(selector)
        await db_session.flush()

        # Create a job for this domain
        job = Job(url="https://testcompany.com/careers/123", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        processor = JobProcessor(db_session)
        result = await processor.process_job(job.id)

        assert result["success"] is True
        assert result["company_name"] == "Test Company Inc"
        assert result["needs_input"] is False

        # Flush the changes and refresh
        await db_session.flush()
        await db_session.refresh(job)
        assert job.status == JobStatus.COMPLETED
        assert job.company_name == "Test Company Inc"

    @pytest.mark.asyncio
    async def test_process_job_with_known_platform(self, db_session: AsyncSession):
        """Test processing job with a learned platform pattern."""
        # Create a selector for a platform
        selector = SiteSelector(
            domain="newplatform.com",
            site_type=SiteType.PLATFORM,
            platform_name="New Platform",
            url_pattern=r"newplatform\.com/([^/]+)",
        )
        db_session.add(selector)
        await db_session.flush()

        # Create a job for this platform
        job = Job(url="https://newplatform.com/acme-corp/job/123", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        processor = JobProcessor(db_session)
        result = await processor.process_job(job.id)

        assert result["success"] is True
        assert result["company_name"] == "Acme Corp"
        assert result["needs_input"] is False

        # Flush the changes and refresh
        await db_session.flush()
        await db_session.refresh(job)
        assert job.status == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_process_job_unknown_domain_requests_input(self, db_session: AsyncSession):
        """Test that unknown domains trigger user input request."""
        # Create a job with unknown domain
        job = Job(url="https://unknown-site.com/job/123", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)
        job_id = job.id

        processor = JobProcessor(db_session)
        result = await processor.process_job(job_id)

        assert result["needs_input"] is True
        assert "unknown-site.com" in result["domain"]

        # Flush changes and refresh to see updated status
        await db_session.flush()
        await db_session.refresh(job)
        assert job.status == JobStatus.NEEDS_INPUT

    @pytest.mark.asyncio
    async def test_process_job_not_found(self, db_session: AsyncSession):
        """Test processing non-existent job returns error."""
        processor = JobProcessor(db_session)
        result = await processor.process_job(99999)

        assert result["success"] is False
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    async def test_get_db_selector(self, db_session: AsyncSession):
        """Test that selectors are retrieved from database."""
        # Create a selector in database
        selector = SiteSelector(
            domain="testsite.com",
            site_type=SiteType.COMPANY,
            company_name="Test Site Inc",
        )
        db_session.add(selector)
        await db_session.flush()

        processor = JobProcessor(db_session)
        result = await processor._get_db_selector("testsite.com")

        assert result is not None
        assert result.company_name == "Test Site Inc"
        assert result.site_type == SiteType.COMPANY

    @pytest.mark.asyncio
    async def test_get_db_selector_returns_none_for_unknown(self, db_session: AsyncSession):
        """Test that unknown domains return None."""
        processor = JobProcessor(db_session)
        result = await processor._get_db_selector("totally-unknown-domain-xyz.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_submit_company_info_as_company_site(self, db_session: AsyncSession):
        """Test submitting company info for a company website."""
        # Create a job in NEEDS_INPUT status
        job = Job(
            url="https://newcompany.com/careers/123",
            status=JobStatus.NEEDS_INPUT
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        processor = JobProcessor(db_session)
        result = await processor.submit_company_info(
            job_id=job.id,
            company_name="New Company Inc",
            site_type="company",
        )

        assert result["success"] is True
        assert result["company_name"] == "New Company Inc"

        # Flush and refresh to see updated status
        await db_session.flush()
        await db_session.refresh(job)
        assert job.status == JobStatus.COMPLETED
        assert job.company_name == "New Company Inc"

        # Check selector was saved
        from sqlalchemy import select
        selector_result = await db_session.execute(
            select(SiteSelector).where(SiteSelector.domain == "newcompany.com")
        )
        saved_selector = selector_result.scalar_one_or_none()

        assert saved_selector is not None
        assert saved_selector.site_type == SiteType.COMPANY
        assert saved_selector.company_name == "New Company Inc"

    @pytest.mark.asyncio
    async def test_submit_company_info_as_platform(self, db_session: AsyncSession):
        """Test submitting company info for a job platform."""
        # Create a job in NEEDS_INPUT status
        job = Job(
            url="https://jobs.newplatform.io/coolstartup/engineer/456",
            status=JobStatus.NEEDS_INPUT
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        processor = JobProcessor(db_session)
        result = await processor.submit_company_info(
            job_id=job.id,
            company_name="Cool Startup",
            site_type="platform",
            platform_name="New Platform",
        )

        assert result["success"] is True
        assert result["company_name"] == "Cool Startup"

        # Flush and refresh
        await db_session.flush()
        await db_session.refresh(job)
        assert job.status == JobStatus.COMPLETED

        # Check selector was saved with pattern
        from sqlalchemy import select
        selector_result = await db_session.execute(
            select(SiteSelector).where(SiteSelector.domain == "jobs.newplatform.io")
        )
        saved_selector = selector_result.scalar_one_or_none()

        assert saved_selector is not None
        assert saved_selector.site_type == SiteType.PLATFORM
        assert saved_selector.platform_name == "New Platform"
        assert saved_selector.url_pattern is not None

    @pytest.mark.asyncio
    async def test_submit_company_wrong_status(self, db_session: AsyncSession):
        """Test that submitting company for non-NEEDS_INPUT job fails."""
        # Create a job in PENDING status
        job = Job(url="https://example.com/job", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        processor = JobProcessor(db_session)
        result = await processor.submit_company_info(
            job_id=job.id,
            company_name="Some Company",
            site_type="company",
        )

        assert result["success"] is False
        assert "not waiting for input" in result["message"]

    @pytest.mark.asyncio
    async def test_submit_company_job_not_found(self, db_session: AsyncSession):
        """Test submitting company for non-existent job."""
        processor = JobProcessor(db_session)
        result = await processor.submit_company_info(
            job_id=99999,
            company_name="Company",
            site_type="company",
        )

        assert result["success"] is False
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    async def test_extract_domain(self, db_session: AsyncSession):
        """Test domain extraction from URLs."""
        processor = JobProcessor(db_session)

        # Test various URL formats
        assert processor.parser.extract_domain("https://linkedin.com/jobs/123") == "linkedin.com"
        assert processor.parser.extract_domain("https://www.indeed.com/job/456") == "indeed.com"
        assert processor.parser.extract_domain("http://careers.google.com/jobs") == "careers.google.com"
        assert processor.parser.extract_domain("invalid-url") == ""

    @pytest.mark.asyncio
    async def test_activity_logged_on_needs_input(self, db_session: AsyncSession):
        """Test that activity is logged when user input is needed."""
        job = Job(url="https://unknown-domain.com/job", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        processor = JobProcessor(db_session)
        await processor.process_job(job.id)

        # Check activity log
        from sqlalchemy import select
        result = await db_session.execute(
            select(ActivityLog).where(ActivityLog.job_id == job.id)
        )
        logs = result.scalars().all()

        # Should have at least one COMPANY_INPUT_NEEDED log
        input_needed_logs = [
            log for log in logs
            if log.action_type == ActionType.COMPANY_INPUT_NEEDED
        ]
        assert len(input_needed_logs) >= 1


class TestPreconfiguredPlatforms:
    """Tests for pre-configured job platforms."""

    @pytest.mark.asyncio
    async def test_greenhouse_url_extraction(self, db_session: AsyncSession):
        """Test extracting company from Greenhouse URL."""
        job = Job(
            url="https://boards.greenhouse.io/acmecorp/jobs/12345",
            status=JobStatus.PENDING
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        processor = JobProcessor(db_session)
        result = await processor.process_job(job.id)

        assert result["success"] is True
        assert result["company_name"] == "Acmecorp"
        assert result["needs_input"] is False

    @pytest.mark.asyncio
    async def test_lever_url_extraction(self, db_session: AsyncSession):
        """Test extracting company from Lever URL."""
        job = Job(
            url="https://jobs.lever.co/awesome-startup/position/123",
            status=JobStatus.PENDING
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        processor = JobProcessor(db_session)
        result = await processor.process_job(job.id)

        assert result["success"] is True
        assert result["company_name"] == "Awesome Startup"
        assert result["needs_input"] is False

    @pytest.mark.asyncio
    async def test_workday_url_extraction(self, db_session: AsyncSession):
        """Test extracting company from Workday URL."""
        job = Job(
            url="https://bigcorp.wd5.myworkdayjobs.com/en-US/careers/job/12345",
            status=JobStatus.PENDING
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        processor = JobProcessor(db_session)
        result = await processor.process_job(job.id)

        assert result["success"] is True
        assert result["company_name"] == "Bigcorp"
        assert result["needs_input"] is False

    @pytest.mark.asyncio
    async def test_platform_with_invalid_url_pattern(self, db_session: AsyncSession):
        """Test that platform with non-matching URL falls back to user input."""
        # This URL doesn't match the expected pattern for greenhouse
        job = Job(
            url="https://greenhouse.io/invalid/path",
            status=JobStatus.PENDING
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        processor = JobProcessor(db_session)
        result = await processor.process_job(job.id)

        # Should fall back to requesting user input
        assert result["needs_input"] is True


class TestURLPatternGeneration:
    """Tests for URL pattern learning."""

    @pytest.mark.asyncio
    async def test_generate_pattern_from_subdomain(self, db_session: AsyncSession):
        """Test generating pattern when company is in subdomain."""
        processor = JobProcessor(db_session)

        url = "https://acme-corp.jobsite.com/careers/123"
        pattern = processor._generate_url_pattern(url, "Acme Corp")

        assert pattern is not None
        # Pattern should match subdomain
        import re
        match = re.search(pattern, url, re.IGNORECASE)
        assert match is not None

    @pytest.mark.asyncio
    async def test_generate_pattern_from_path(self, db_session: AsyncSession):
        """Test generating pattern when company is in URL path."""
        processor = JobProcessor(db_session)

        url = "https://jobs.platform.io/acme-corp/engineer/456"
        pattern = processor._generate_url_pattern(url, "Acme Corp")

        assert pattern is not None
        # Pattern should extract from path
        import re
        match = re.search(pattern, url, re.IGNORECASE)
        assert match is not None

    @pytest.mark.asyncio
    async def test_pattern_reuse_for_new_urls(self, db_session: AsyncSession):
        """Test that learned patterns work for new URLs from same platform."""
        # First, submit a job and learn the pattern
        job1 = Job(
            url="https://jobs.newjobsite.com/first-company/position/123",
            status=JobStatus.NEEDS_INPUT
        )
        db_session.add(job1)
        await db_session.flush()
        await db_session.refresh(job1)

        processor = JobProcessor(db_session)
        await processor.submit_company_info(
            job_id=job1.id,
            company_name="First Company",
            site_type="platform",
            platform_name="New Job Site",
        )
        await db_session.flush()

        # Now submit another job from same platform
        job2 = Job(
            url="https://jobs.newjobsite.com/second-company/position/456",
            status=JobStatus.PENDING
        )
        db_session.add(job2)
        await db_session.flush()
        await db_session.refresh(job2)

        result = await processor.process_job(job2.id)

        # Should extract company from URL using learned pattern
        assert result["success"] is True
        assert result["company_name"] == "Second Company"
        assert result["needs_input"] is False


class TestLegacyCompatibility:
    """Tests for backward compatibility."""

    @pytest.mark.asyncio
    async def test_submit_company_name_legacy_method(self, db_session: AsyncSession):
        """Test that legacy submit_company_name method still works."""
        job = Job(
            url="https://oldsite.com/job/123",
            status=JobStatus.NEEDS_INPUT
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        processor = JobProcessor(db_session)
        result = await processor.submit_company_name(
            job_id=job.id,
            company_name="Old Company",
        )

        assert result["success"] is True
        assert result["company_name"] == "Old Company"
