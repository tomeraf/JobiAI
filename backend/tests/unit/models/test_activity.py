"""
Unit tests for ActivityLog model.
"""
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.activity import ActivityLog, ActionType
from app.models.job import Job, JobStatus


class TestActivityLogModel:
    """Tests for the ActivityLog model."""

    def test_action_type_enum_values(self):
        """Test that ActionType enum has expected values."""
        assert ActionType.JOB_SUBMITTED.value == "job_submitted"
        assert ActionType.COMPANY_EXTRACTED.value == "company_extracted"
        assert ActionType.SELECTOR_LEARNED.value == "selector_learned"
        assert ActionType.CONNECTION_SEARCH.value == "connection_search"
        assert ActionType.CONNECTION_FOUND.value == "connection_found"
        assert ActionType.CONNECTION_REQUEST_SENT.value == "connection_request_sent"
        assert ActionType.MESSAGE_SENT.value == "message_sent"
        assert ActionType.LINKEDIN_SEARCH.value == "linkedin_search"
        assert ActionType.ERROR.value == "error"

    @pytest.mark.asyncio
    async def test_create_activity_log(self, db_session: AsyncSession):
        """Test creating a new activity log."""
        log = ActivityLog(
            action_type=ActionType.JOB_SUBMITTED,
            description="New job submitted"
        )
        db_session.add(log)
        await db_session.flush()
        await db_session.refresh(log)

        assert log.id is not None
        assert log.action_type == ActionType.JOB_SUBMITTED
        assert log.description == "New job submitted"
        assert log.created_at is not None
        assert log.details is None
        assert log.job_id is None

    @pytest.mark.asyncio
    async def test_activity_log_with_details(self, db_session: AsyncSession):
        """Test creating an activity log with JSON details."""
        log = ActivityLog(
            action_type=ActionType.COMPANY_EXTRACTED,
            description="Company extracted from job URL",
            details={
                "url": "https://example.com/job",
                "company": "Test Company",
                "title": "Software Engineer"
            }
        )
        db_session.add(log)
        await db_session.flush()
        await db_session.refresh(log)

        assert log.details is not None
        assert log.details["company"] == "Test Company"
        assert log.details["title"] == "Software Engineer"

    @pytest.mark.asyncio
    async def test_activity_log_with_job_reference(self, db_session: AsyncSession, sample_job: Job):
        """Test activity log linked to a job."""
        log = ActivityLog(
            action_type=ActionType.MESSAGE_SENT,
            description="Message sent to connection",
            job_id=sample_job.id
        )
        db_session.add(log)
        await db_session.flush()
        await db_session.refresh(log)

        assert log.job_id == sample_job.id

    @pytest.mark.asyncio
    async def test_activity_log_error_type(self, db_session: AsyncSession):
        """Test creating an error activity log."""
        log = ActivityLog(
            action_type=ActionType.ERROR,
            description="Failed to connect to LinkedIn",
            details={
                "error_type": "ConnectionError",
                "message": "Network timeout",
                "retry_count": 3
            }
        )
        db_session.add(log)
        await db_session.flush()
        await db_session.refresh(log)

        assert log.action_type == ActionType.ERROR
        assert log.details["retry_count"] == 3

    @pytest.mark.asyncio
    async def test_activity_log_repr(self, db_session: AsyncSession):
        """Test activity log string representation."""
        log = ActivityLog(
            action_type=ActionType.CONNECTION_FOUND,
            description="Found 5 connections at target company"
        )
        db_session.add(log)
        await db_session.flush()
        await db_session.refresh(log)

        repr_str = repr(log)
        assert "ActivityLog" in repr_str
        assert "CONNECTION_FOUND" in repr_str or "connection_found" in repr_str.lower()

    @pytest.mark.asyncio
    async def test_activity_log_long_description_truncated_in_repr(self, db_session: AsyncSession):
        """Test that long descriptions are truncated in repr."""
        long_desc = "A" * 100
        log = ActivityLog(
            action_type=ActionType.JOB_SUBMITTED,
            description=long_desc
        )
        db_session.add(log)
        await db_session.flush()
        await db_session.refresh(log)

        repr_str = repr(log)
        # Repr should truncate to 50 chars
        assert len(repr_str) < len(long_desc) + 50


class TestActivityLogQueries:
    """Tests for activity log database queries."""

    @pytest.mark.asyncio
    async def test_query_logs_by_action_type(self, db_session: AsyncSession):
        """Test querying logs by action type."""
        logs = [
            ActivityLog(action_type=ActionType.JOB_SUBMITTED, description="Job 1"),
            ActivityLog(action_type=ActionType.MESSAGE_SENT, description="Message 1"),
            ActivityLog(action_type=ActionType.JOB_SUBMITTED, description="Job 2"),
            ActivityLog(action_type=ActionType.ERROR, description="Error 1"),
        ]
        db_session.add_all(logs)
        await db_session.flush()

        result = await db_session.execute(
            select(ActivityLog).where(ActivityLog.action_type == ActionType.JOB_SUBMITTED)
        )
        job_logs = result.scalars().all()

        assert len(job_logs) == 2
        for log in job_logs:
            assert log.action_type == ActionType.JOB_SUBMITTED

    @pytest.mark.asyncio
    async def test_query_logs_by_job_id(self, db_session: AsyncSession, sample_job: Job):
        """Test querying logs for a specific job."""
        logs = [
            ActivityLog(action_type=ActionType.JOB_SUBMITTED, description="Job submitted", job_id=sample_job.id),
            ActivityLog(action_type=ActionType.COMPANY_EXTRACTED, description="Company extracted", job_id=sample_job.id),
            ActivityLog(action_type=ActionType.MESSAGE_SENT, description="Unrelated log"),
        ]
        db_session.add_all(logs)
        await db_session.flush()

        result = await db_session.execute(
            select(ActivityLog).where(ActivityLog.job_id == sample_job.id)
        )
        job_logs = result.scalars().all()

        assert len(job_logs) == 2
        for log in job_logs:
            assert log.job_id == sample_job.id

    @pytest.mark.asyncio
    async def test_query_logs_ordered_by_date(self, db_session: AsyncSession):
        """Test querying logs ordered by ID (proxy for creation order in test)."""
        logs = [
            ActivityLog(action_type=ActionType.JOB_SUBMITTED, description="First"),
            ActivityLog(action_type=ActionType.MESSAGE_SENT, description="Second"),
            ActivityLog(action_type=ActionType.ERROR, description="Third"),
        ]
        db_session.add_all(logs)
        await db_session.flush()

        result = await db_session.execute(
            select(ActivityLog).order_by(ActivityLog.id.desc())
        )
        ordered_logs = result.scalars().all()

        assert len(ordered_logs) >= 3
        # Most recent (highest ID) should be first
        assert ordered_logs[0].description == "Third"

    @pytest.mark.asyncio
    async def test_count_errors(self, db_session: AsyncSession):
        """Test counting error logs."""
        from sqlalchemy import func

        logs = [
            ActivityLog(action_type=ActionType.ERROR, description="Error 1"),
            ActivityLog(action_type=ActionType.ERROR, description="Error 2"),
            ActivityLog(action_type=ActionType.JOB_SUBMITTED, description="Job"),
        ]
        db_session.add_all(logs)
        await db_session.flush()

        result = await db_session.execute(
            select(func.count(ActivityLog.id)).where(ActivityLog.action_type == ActionType.ERROR)
        )
        error_count = result.scalar()

        assert error_count == 2


class TestActionTypeEnum:
    """Tests for ActionType enum."""

    def test_all_action_types_exist(self):
        """Verify all expected action types exist."""
        expected = {
            "job_submitted", "company_extracted", "company_input_needed",
            "selector_learned", "connection_search", "connection_found",
            "connection_request_sent", "message_sent", "linkedin_search", "error"
        }
        actual = {a.value for a in ActionType}
        assert actual == expected

    def test_action_type_from_string(self):
        """Test creating action type from string value."""
        assert ActionType("job_submitted") == ActionType.JOB_SUBMITTED
        assert ActionType("error") == ActionType.ERROR

    def test_invalid_action_type_raises(self):
        """Test that invalid action type raises ValueError."""
        with pytest.raises(ValueError):
            ActionType("invalid_action")
