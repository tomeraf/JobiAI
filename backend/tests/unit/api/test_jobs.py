"""
Unit tests for Jobs API routes.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.models.activity import ActivityLog, ActionType


class TestCreateJob:
    """Tests for POST /api/jobs endpoint."""

    @pytest.mark.asyncio
    async def test_create_job_success(self, client: AsyncClient):
        """Test successfully creating a job."""
        response = await client.post(
            "/api/jobs",
            json={"url": "https://linkedin.com/jobs/123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "https://linkedin.com/jobs/123"
        assert data["status"] == "pending"
        assert data["id"] is not None

    @pytest.mark.asyncio
    async def test_create_job_logs_activity(self, client: AsyncClient, db_session: AsyncSession):
        """Test that creating a job logs activity."""
        response = await client.post(
            "/api/jobs",
            json={"url": "https://example.com/job"}
        )

        assert response.status_code == 200
        job_id = response.json()["id"]

        # Check activity was logged
        from sqlalchemy import select
        result = await db_session.execute(
            select(ActivityLog).where(ActivityLog.job_id == job_id)
        )
        logs = result.scalars().all()
        assert len(logs) >= 1
        assert any(log.action_type == ActionType.JOB_SUBMITTED for log in logs)

    @pytest.mark.asyncio
    async def test_create_job_missing_url(self, client: AsyncClient):
        """Test creating job without URL fails."""
        response = await client.post(
            "/api/jobs",
            json={}
        )

        assert response.status_code == 422  # Validation error


class TestListJobs:
    """Tests for GET /api/jobs endpoint."""

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, client: AsyncClient):
        """Test listing jobs when none exist."""
        response = await client.get("/api/jobs")

        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert "total" in data
        assert isinstance(data["jobs"], list)

    @pytest.mark.asyncio
    async def test_list_jobs_with_data(self, client: AsyncClient, sample_job: Job):
        """Test listing jobs with existing data."""
        response = await client.get("/api/jobs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) >= 1

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_status(self, client: AsyncClient, db_session: AsyncSession):
        """Test filtering jobs by status."""
        # Create jobs with different statuses
        pending_job = Job(url="https://example.com/1", status=JobStatus.PENDING)
        completed_job = Job(url="https://example.com/2", status=JobStatus.COMPLETED)
        db_session.add_all([pending_job, completed_job])
        await db_session.flush()

        response = await client.get("/api/jobs?status=pending")

        assert response.status_code == 200
        data = response.json()
        for job in data["jobs"]:
            assert job["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_jobs_invalid_status(self, client: AsyncClient):
        """Test filtering with invalid status."""
        response = await client.get("/api/jobs?status=invalid")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_jobs_pagination(self, client: AsyncClient, db_session: AsyncSession):
        """Test job list pagination."""
        # Create multiple jobs
        jobs = [Job(url=f"https://example.com/{i}") for i in range(10)]
        db_session.add_all(jobs)
        await db_session.flush()

        response = await client.get("/api/jobs?skip=0&limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) <= 5


class TestGetJob:
    """Tests for GET /api/jobs/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_job_success(self, client: AsyncClient, sample_job: Job):
        """Test getting a specific job."""
        response = await client.get(f"/api/jobs/{sample_job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_job.id
        assert data["url"] == sample_job.url

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, client: AsyncClient):
        """Test getting non-existent job."""
        response = await client.get("/api/jobs/99999")

        assert response.status_code == 404


class TestDeleteJob:
    """Tests for DELETE /api/jobs/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_job_success(self, client: AsyncClient, sample_job: Job):
        """Test deleting a job."""
        response = await client.delete(f"/api/jobs/{sample_job.id}")

        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_delete_job_not_found(self, client: AsyncClient):
        """Test deleting non-existent job."""
        response = await client.delete("/api/jobs/99999")

        assert response.status_code == 404


class TestRetryJob:
    """Tests for POST /api/jobs/{job_id}/retry endpoint."""

    @pytest.mark.asyncio
    async def test_retry_failed_job(self, client: AsyncClient, db_session: AsyncSession):
        """Test retrying a failed job."""
        # Create a failed job
        job = Job(url="https://example.com/failed", status=JobStatus.FAILED, error_message="Test error")
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await client.post(f"/api/jobs/{job.id}/retry")

        assert response.status_code == 200
        assert "retry" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_retry_pending_job_fails(self, client: AsyncClient, sample_job: Job):
        """Test that retrying a non-failed job fails."""
        # sample_job is PENDING by default
        response = await client.post(f"/api/jobs/{sample_job.id}/retry")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_retry_job_not_found(self, client: AsyncClient):
        """Test retrying non-existent job."""
        response = await client.post("/api/jobs/99999/retry")

        assert response.status_code == 404


class TestSubmitCompany:
    """Tests for POST /api/jobs/{job_id}/company endpoint."""

    @pytest.mark.asyncio
    async def test_submit_company_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test successfully submitting company name."""
        # Create a job in NEEDS_INPUT status
        job = Job(url="https://unknown-site.com/job/123", status=JobStatus.NEEDS_INPUT)
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await client.post(
            f"/api/jobs/{job.id}/company",
            json={"company_name": "Test Company Inc"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["company_name"] == "Test Company Inc"
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_submit_company_with_selector(self, client: AsyncClient, db_session: AsyncSession):
        """Test submitting company name with a CSS selector."""
        job = Job(url="https://newsite.com/careers/456", status=JobStatus.NEEDS_INPUT)
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await client.post(
            f"/api/jobs/{job.id}/company",
            json={
                "company_name": "Awesome Corp",
                "company_selector": ".employer-name"
            }
        )

        assert response.status_code == 200
        assert response.json()["company_name"] == "Awesome Corp"

    @pytest.mark.asyncio
    async def test_submit_company_wrong_status(self, client: AsyncClient, sample_job: Job):
        """Test that submitting company for non-NEEDS_INPUT job fails."""
        # sample_job is PENDING by default
        response = await client.post(
            f"/api/jobs/{sample_job.id}/company",
            json={"company_name": "Some Company"}
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_submit_company_not_found(self, client: AsyncClient):
        """Test submitting company for non-existent job."""
        response = await client.post(
            "/api/jobs/99999/company",
            json={"company_name": "Company"}
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_submit_company_missing_name(self, client: AsyncClient, db_session: AsyncSession):
        """Test that missing company name fails validation."""
        job = Job(url="https://site.com/job", status=JobStatus.NEEDS_INPUT)
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await client.post(
            f"/api/jobs/{job.id}/company",
            json={}
        )

        assert response.status_code == 422


class TestTriggerProcess:
    """Tests for POST /api/jobs/{job_id}/process endpoint."""

    @pytest.mark.asyncio
    async def test_trigger_process_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test triggering job processing."""
        job = Job(url="https://example.com/job", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await client.post(f"/api/jobs/{job.id}/process")

        assert response.status_code == 200
        assert "triggered" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_trigger_process_already_processing(self, client: AsyncClient, db_session: AsyncSession):
        """Test that triggering process on already processing job fails."""
        job = Job(url="https://example.com/job", status=JobStatus.PROCESSING)
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await client.post(f"/api/jobs/{job.id}/process")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_trigger_process_not_found(self, client: AsyncClient):
        """Test triggering process for non-existent job."""
        response = await client.post("/api/jobs/99999/process")

        assert response.status_code == 404
