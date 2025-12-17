"""
Unit tests for Job model.
"""
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.job import Job, JobStatus


class TestJobModel:
    """Tests for the Job model."""

    def test_job_status_enum_values(self):
        """Test that JobStatus enum has expected values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.PROCESSING.value == "processing"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"

    def test_job_status_is_string_enum(self):
        """Test that JobStatus values work as strings."""
        assert str(JobStatus.PENDING) == "JobStatus.PENDING"
        assert JobStatus.PENDING == "pending"

    @pytest.mark.asyncio
    async def test_create_job(self, db_session: AsyncSession):
        """Test creating a new job."""
        job = Job(
            url="https://example.com/job/1",
            status=JobStatus.PENDING
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        assert job.id is not None
        assert job.url == "https://example.com/job/1"
        assert job.status == JobStatus.PENDING
        assert job.company_name is None
        assert job.job_title is None
        assert job.error_message is None
        assert job.created_at is not None
        assert job.processed_at is None

    @pytest.mark.asyncio
    async def test_job_default_status(self, db_session: AsyncSession):
        """Test that job defaults to PENDING status."""
        job = Job(url="https://example.com/job/2")
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        assert job.status == JobStatus.PENDING

    @pytest.mark.asyncio
    async def test_job_with_company_info(self, db_session: AsyncSession):
        """Test creating a job with company information."""
        job = Job(
            url="https://linkedin.com/jobs/123",
            company_name="Google",
            job_title="Software Engineer",
            status=JobStatus.COMPLETED
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        assert job.company_name == "Google"
        assert job.job_title == "Software Engineer"
        assert job.status == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_job_with_error(self, db_session: AsyncSession):
        """Test creating a failed job with error message."""
        job = Job(
            url="https://invalid.com/job",
            status=JobStatus.FAILED,
            error_message="Could not extract company name"
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        assert job.status == JobStatus.FAILED
        assert job.error_message == "Could not extract company name"

    @pytest.mark.asyncio
    async def test_job_created_at_auto_set(self, db_session: AsyncSession):
        """Test that created_at is automatically set."""
        before = datetime.utcnow()
        job = Job(url="https://example.com/job/3")
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)
        after = datetime.utcnow()

        assert job.created_at >= before
        assert job.created_at <= after

    @pytest.mark.asyncio
    async def test_job_repr(self, db_session: AsyncSession):
        """Test job string representation."""
        job = Job(
            url="https://example.com/job",
            company_name="TestCo",
            status=JobStatus.PENDING
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        repr_str = repr(job)
        assert "Job" in repr_str
        assert "TestCo" in repr_str
        assert "PENDING" in repr_str or "pending" in repr_str.lower()

    @pytest.mark.asyncio
    async def test_job_status_transition(self, db_session: AsyncSession):
        """Test changing job status."""
        job = Job(url="https://example.com/job/4")
        db_session.add(job)
        await db_session.flush()

        assert job.status == JobStatus.PENDING

        job.status = JobStatus.PROCESSING
        await db_session.flush()
        assert job.status == JobStatus.PROCESSING

        job.status = JobStatus.COMPLETED
        job.processed_at = datetime.utcnow()
        await db_session.flush()
        assert job.status == JobStatus.COMPLETED
        assert job.processed_at is not None

    @pytest.mark.asyncio
    async def test_query_jobs_by_status(self, db_session: AsyncSession):
        """Test querying jobs by status."""
        # Create jobs with different statuses
        job1 = Job(url="https://example.com/1", status=JobStatus.PENDING)
        job2 = Job(url="https://example.com/2", status=JobStatus.COMPLETED)
        job3 = Job(url="https://example.com/3", status=JobStatus.PENDING)

        db_session.add_all([job1, job2, job3])
        await db_session.flush()

        # Query pending jobs
        result = await db_session.execute(
            select(Job).where(Job.status == JobStatus.PENDING)
        )
        pending_jobs = result.scalars().all()

        assert len(pending_jobs) == 2
        for job in pending_jobs:
            assert job.status == JobStatus.PENDING


class TestJobStatusEnum:
    """Tests for JobStatus enum edge cases."""

    def test_all_status_values_exist(self):
        """Verify all expected status values exist."""
        expected = {"pending", "processing", "needs_input", "completed", "failed"}
        actual = {s.value for s in JobStatus}
        assert actual == expected

    def test_status_from_string(self):
        """Test creating status from string value."""
        status = JobStatus("pending")
        assert status == JobStatus.PENDING

    def test_invalid_status_raises(self):
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError):
            JobStatus("invalid_status")
