"""
Integration tests for job submission and company extraction.

Tests the ACTUAL JobProcessor logic:
1. Company extraction from known platforms (Greenhouse, Lever, etc.)
2. Company extraction from database selectors
3. Unknown site flow (NEEDS_INPUT)
4. User providing company info and learning patterns
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.job import Job, JobStatus
from app.models.site_selector import SiteSelector, SiteType
from app.models.activity import ActivityLog, ActionType
from app.services.job_processor import JobProcessor


class TestJobProcessorCompanyExtraction:
    """Test JobProcessor.process_job() with real logic."""

    @pytest.mark.asyncio
    async def test_extract_company_from_lever_url(self, db_session: AsyncSession):
        """Should extract company from Lever path pattern."""
        job = Job(url="https://jobs.lever.co/acme/12345", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.flush()

        processor = JobProcessor(db_session)
        result = await processor.process_job(job.id)

        assert result["success"] is True
        # Company name gets title-cased
        assert result["company_name"].lower() == "acme"

    @pytest.mark.asyncio
    async def test_extract_company_from_workday_url(self, db_session: AsyncSession):
        """Should extract company from Workday subdomain pattern."""
        job = Job(url="https://acme.wd5.myworkdayjobs.com/careers/job/123", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.flush()

        processor = JobProcessor(db_session)
        result = await processor.process_job(job.id)

        assert result["success"] is True
        assert result["company_name"].lower() == "acme"

    @pytest.mark.asyncio
    async def test_extract_company_from_ashby_url(self, db_session: AsyncSession):
        """Should extract company from Ashby path pattern."""
        job = Job(url="https://jobs.ashbyhq.com/acme/12345", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.flush()

        processor = JobProcessor(db_session)
        result = await processor.process_job(job.id)

        assert result["success"] is True
        assert result["company_name"].lower() == "acme"


class TestJobProcessorDatabaseSelectors:
    """Test JobProcessor with database-stored selectors."""

    @pytest.mark.asyncio
    async def test_use_company_site_selector(self, db_session: AsyncSession):
        """Should use saved company site selector."""
        # Create selector for a company site
        # JobProcessor looks up by exact domain match
        selector = SiteSelector(
            domain="careers.techcorp.com",
            site_type=SiteType.COMPANY,
            company_name="TechCorp Inc"
        )
        db_session.add(selector)
        await db_session.commit()  # Commit to ensure selector is visible

        # Create job from that domain
        job = Job(url="https://careers.techcorp.com/jobs/456", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.commit()

        processor = JobProcessor(db_session)
        result = await processor.process_job(job.id)
        await db_session.commit()  # Commit processor changes

        assert result["success"] is True
        assert result["company_name"] == "TechCorp Inc"

        await db_session.refresh(job)
        assert job.company_name == "TechCorp Inc"
        assert job.status == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_selector_for_known_company_returns_company_name(self, db_session: AsyncSession):
        """Company site selector should return fixed company name."""
        selector = SiteSelector(
            domain="jobs.mycompany.com",
            site_type=SiteType.COMPANY,
            company_name="My Company Inc"
        )
        db_session.add(selector)
        await db_session.commit()

        job = Job(url="https://jobs.mycompany.com/careers/123", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.commit()

        processor = JobProcessor(db_session)
        result = await processor.process_job(job.id)
        await db_session.commit()

        assert result["success"] is True
        assert result["company_name"] == "My Company Inc"


class TestJobProcessorUnknownSites:
    """Test JobProcessor with unknown sites."""

    @pytest.mark.asyncio
    async def test_unknown_site_sets_needs_input(self, db_session: AsyncSession):
        """Unknown site should set NEEDS_INPUT status."""
        job = Job(url="https://unknown-company.com/jobs/123", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.commit()

        processor = JobProcessor(db_session)
        result = await processor.process_job(job.id)
        await db_session.commit()

        assert result["success"] is True
        assert result["needs_input"] is True
        assert "unknown-company.com" in result.get("domain", "")

        await db_session.refresh(job)
        assert job.status == JobStatus.NEEDS_INPUT

    @pytest.mark.asyncio
    async def test_unknown_site_logs_activity(self, db_session: AsyncSession):
        """Unknown site should create COMPANY_INPUT_NEEDED activity."""
        job = Job(url="https://unknown-company.com/jobs/123", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.flush()

        processor = JobProcessor(db_session)
        await processor.process_job(job.id)

        # Check activity log
        result = await db_session.execute(
            select(ActivityLog).where(
                ActivityLog.job_id == job.id,
                ActivityLog.action_type == ActionType.COMPANY_INPUT_NEEDED
            )
        )
        log = result.scalar_one_or_none()
        assert log is not None


class TestJobProcessorSubmitCompanyInfo:
    """Test user submitting company info for unknown sites."""

    @pytest.mark.asyncio
    async def test_submit_company_info_updates_job(self, db_session: AsyncSession):
        """Submitting company info should update job."""
        job = Job(url="https://unknown-company.com/jobs/123", status=JobStatus.NEEDS_INPUT)
        db_session.add(job)
        await db_session.flush()

        processor = JobProcessor(db_session)
        result = await processor.submit_company_info(
            job_id=job.id,
            company_name="Unknown Corp",
            site_type="company"
        )

        assert result["success"] is True
        assert result["company_name"] == "Unknown Corp"

        await db_session.refresh(job)
        assert job.company_name == "Unknown Corp"
        assert job.status == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_submit_company_info_learns_pattern(self, db_session: AsyncSession):
        """Submitting company info should save selector for future."""
        job = Job(url="https://careers.newcorp.com/jobs/123", status=JobStatus.NEEDS_INPUT)
        db_session.add(job)
        await db_session.flush()

        processor = JobProcessor(db_session)
        await processor.submit_company_info(
            job_id=job.id,
            company_name="NewCorp",
            site_type="company"
        )

        # Check selector was created
        result = await db_session.execute(
            select(SiteSelector).where(SiteSelector.domain == "careers.newcorp.com")
        )
        selector = result.scalar_one_or_none()
        assert selector is not None
        assert selector.company_name == "NewCorp"
        assert selector.site_type == SiteType.COMPANY

    @pytest.mark.asyncio
    async def test_submit_platform_info_learns_url_pattern(self, db_session: AsyncSession):
        """Submitting platform info should generate URL pattern."""
        job = Job(url="https://newcorp.customplatform.io/jobs/123", status=JobStatus.NEEDS_INPUT)
        db_session.add(job)
        await db_session.flush()

        processor = JobProcessor(db_session)
        await processor.submit_company_info(
            job_id=job.id,
            company_name="newcorp",
            site_type="platform",
            platform_name="CustomPlatform"
        )

        # Check selector was created with pattern
        result = await db_session.execute(
            select(SiteSelector).where(SiteSelector.domain == "newcorp.customplatform.io")
        )
        selector = result.scalar_one_or_none()
        assert selector is not None
        assert selector.platform_name == "CustomPlatform"
        assert selector.site_type == SiteType.PLATFORM
        # URL pattern should be generated for subdomain extraction
        assert selector.url_pattern is not None

    @pytest.mark.asyncio
    async def test_future_jobs_use_learned_selector(self, db_session: AsyncSession):
        """Future jobs should use the learned selector."""
        # First job - teach the system
        job1 = Job(url="https://careers.newcorp.com/jobs/123", status=JobStatus.NEEDS_INPUT)
        db_session.add(job1)
        await db_session.flush()

        processor = JobProcessor(db_session)
        await processor.submit_company_info(
            job_id=job1.id,
            company_name="NewCorp",
            site_type="company"
        )

        # Second job - should auto-extract
        job2 = Job(url="https://careers.newcorp.com/jobs/456", status=JobStatus.PENDING)
        db_session.add(job2)
        await db_session.flush()

        result = await processor.process_job(job2.id)

        assert result["success"] is True
        assert result["company_name"] == "NewCorp"
        assert result["needs_input"] is False


class TestJobProcessorEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_process_nonexistent_job(self, db_session: AsyncSession):
        """Processing nonexistent job should fail gracefully."""
        processor = JobProcessor(db_session)
        result = await processor.process_job(99999)

        assert result["success"] is False
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_submit_info_wrong_status(self, db_session: AsyncSession):
        """Submitting info when job is not NEEDS_INPUT should fail."""
        job = Job(url="https://example.com/jobs/123", status=JobStatus.COMPLETED)
        db_session.add(job)
        await db_session.flush()

        processor = JobProcessor(db_session)
        result = await processor.submit_company_info(
            job_id=job.id,
            company_name="Test",
            site_type="company"
        )

        assert result["success"] is False
        assert "not waiting for input" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_invalid_url_fails(self, db_session: AsyncSession):
        """Invalid URL should fail gracefully."""
        job = Job(url="not-a-valid-url", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.commit()

        processor = JobProcessor(db_session)
        result = await processor.process_job(job.id)
        await db_session.commit()

        assert result["success"] is False
        await db_session.refresh(job)
        assert job.status == JobStatus.FAILED


class TestJobAPIEndpoints:
    """Test job-related API endpoints."""

    @pytest.mark.asyncio
    async def test_submit_job_url(self, client: AsyncClient):
        """POST /api/jobs should create a pending job."""
        response = await client.post("/api/jobs", json={"url": "https://acme.greenhouse.io/jobs/123"})

        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "https://acme.greenhouse.io/jobs/123"
        assert data["id"] is not None

    @pytest.mark.asyncio
    async def test_list_jobs(self, client: AsyncClient, pending_job: Job, job_with_company: Job):
        """GET /api/jobs should list all jobs."""
        response = await client.get("/api/jobs")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2

    @pytest.mark.asyncio
    async def test_get_single_job(self, client: AsyncClient, pending_job: Job):
        """GET /api/jobs/{id} should return job details."""
        response = await client.get(f"/api/jobs/{pending_job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == pending_job.id

    @pytest.mark.asyncio
    async def test_delete_job(self, client: AsyncClient, db_session: AsyncSession, pending_job: Job):
        """DELETE /api/jobs/{id} should delete the job."""
        job_id = pending_job.id
        response = await client.delete(f"/api/jobs/{job_id}")

        assert response.status_code == 200

        result = await db_session.execute(select(Job).where(Job.id == job_id))
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_submit_company_via_api(self, client: AsyncClient, job_needs_input: Job):
        """POST /api/jobs/{id}/company should update job."""
        response = await client.post(
            f"/api/jobs/{job_needs_input.id}/company",
            json={"company_name": "TestCorp", "site_type": "company"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["company_name"] == "TestCorp"
