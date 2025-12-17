"""
Unit tests for Logs API routes.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivityLog, ActionType
from app.models.job import Job


class TestListLogs:
    """Tests for GET /api/logs endpoint."""

    @pytest.mark.asyncio
    async def test_list_logs_empty(self, client: AsyncClient):
        """Test listing logs when none exist."""
        response = await client.get("/api/logs")

        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
        assert isinstance(data["logs"], list)

    @pytest.mark.asyncio
    async def test_list_logs_with_data(self, client: AsyncClient, sample_activity_log: ActivityLog):
        """Test listing logs with existing data."""
        response = await client.get("/api/logs")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["logs"]) >= 1

    @pytest.mark.asyncio
    async def test_list_logs_filter_by_action_type(
        self,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test filtering logs by action type."""
        # Create logs with different action types
        log1 = ActivityLog(action_type=ActionType.JOB_SUBMITTED, description="Job 1")
        log2 = ActivityLog(action_type=ActionType.MESSAGE_SENT, description="Message 1")
        log3 = ActivityLog(action_type=ActionType.JOB_SUBMITTED, description="Job 2")
        db_session.add_all([log1, log2, log3])
        await db_session.flush()

        response = await client.get("/api/logs?action_type=job_submitted")

        assert response.status_code == 200
        data = response.json()
        for log in data["logs"]:
            assert log["action_type"] == "job_submitted"

    @pytest.mark.asyncio
    async def test_list_logs_filter_by_job_id(
        self,
        client: AsyncClient,
        sample_job: Job,
        sample_activity_log: ActivityLog
    ):
        """Test filtering logs by job ID."""
        response = await client.get(f"/api/logs?job_id={sample_job.id}")

        assert response.status_code == 200
        data = response.json()
        for log in data["logs"]:
            assert log["job_id"] == sample_job.id

    @pytest.mark.asyncio
    async def test_list_logs_pagination(self, client: AsyncClient, db_session: AsyncSession):
        """Test log pagination."""
        # Create multiple logs
        logs = [
            ActivityLog(action_type=ActionType.JOB_SUBMITTED, description=f"Log {i}")
            for i in range(15)
        ]
        db_session.add_all(logs)
        await db_session.flush()

        response = await client.get("/api/logs?skip=0&limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) <= 5

    @pytest.mark.asyncio
    async def test_list_logs_invalid_action_type_ignored(self, client: AsyncClient):
        """Test that invalid action type is ignored (not error)."""
        response = await client.get("/api/logs?action_type=invalid_type")

        # Should not error, just return all logs
        assert response.status_code == 200


class TestGetStats:
    """Tests for GET /api/logs/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, client: AsyncClient):
        """Test getting stats when no logs exist."""
        response = await client.get("/api/logs/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_actions" in data
        assert "jobs_submitted" in data
        assert "messages_sent" in data
        assert "connections_requested" in data
        assert "errors" in data

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting stats with existing data."""
        # Create various logs
        logs = [
            ActivityLog(action_type=ActionType.JOB_SUBMITTED, description="Job 1"),
            ActivityLog(action_type=ActionType.JOB_SUBMITTED, description="Job 2"),
            ActivityLog(action_type=ActionType.MESSAGE_SENT, description="Message 1"),
            ActivityLog(action_type=ActionType.CONNECTION_REQUEST_SENT, description="Connect 1"),
            ActivityLog(action_type=ActionType.ERROR, description="Error 1"),
        ]
        db_session.add_all(logs)
        await db_session.flush()

        response = await client.get("/api/logs/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_actions"] >= 5
        assert data["jobs_submitted"] >= 2
        assert data["messages_sent"] >= 1
        assert data["connections_requested"] >= 1
        assert data["errors"] >= 1


class TestGetRecentLogs:
    """Tests for GET /api/logs/recent endpoint."""

    @pytest.mark.asyncio
    async def test_get_recent_logs_empty(self, client: AsyncClient):
        """Test getting recent logs when none exist."""
        response = await client.get("/api/logs/recent")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_recent_logs_with_data(
        self,
        client: AsyncClient,
        sample_activity_log: ActivityLog
    ):
        """Test getting recent logs with existing data."""
        response = await client.get("/api/logs/recent")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_recent_logs_respects_limit(
        self,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test that recent logs respects limit parameter."""
        # Create many logs
        logs = [
            ActivityLog(action_type=ActionType.JOB_SUBMITTED, description=f"Log {i}")
            for i in range(30)
        ]
        db_session.add_all(logs)
        await db_session.flush()

        response = await client.get("/api/logs/recent?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5

    @pytest.mark.asyncio
    async def test_get_recent_logs_max_limit(self, client: AsyncClient):
        """Test that limit cannot exceed maximum."""
        response = await client.get("/api/logs/recent?limit=200")

        # Should either cap at 100 or return validation error
        assert response.status_code in [200, 422]
        if response.status_code == 200:
            assert len(response.json()) <= 100


class TestGetJobLogs:
    """Tests for GET /api/logs/job/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_job_logs_success(
        self,
        client: AsyncClient,
        sample_job: Job,
        sample_activity_log: ActivityLog
    ):
        """Test getting logs for a specific job."""
        response = await client.get(f"/api/logs/job/{sample_job.id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for log in data:
            assert log["job_id"] == sample_job.id

    @pytest.mark.asyncio
    async def test_get_job_logs_empty(self, client: AsyncClient, sample_job: Job):
        """Test getting logs for job with no logs."""
        # Create a job without logs
        response = await client.get(f"/api/logs/job/{sample_job.id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_job_logs_nonexistent_job(self, client: AsyncClient):
        """Test getting logs for non-existent job returns empty list."""
        response = await client.get("/api/logs/job/99999")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_get_job_logs_ordered_by_date(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        sample_job: Job
    ):
        """Test that job logs are ordered by date (ascending)."""
        # Create multiple logs for the job
        logs = [
            ActivityLog(
                action_type=ActionType.JOB_SUBMITTED,
                description=f"Step {i}",
                job_id=sample_job.id
            )
            for i in range(3)
        ]
        db_session.add_all(logs)
        await db_session.flush()

        response = await client.get(f"/api/logs/job/{sample_job.id}")

        assert response.status_code == 200
        data = response.json()
        # Logs should be ordered by created_at ascending
        if len(data) > 1:
            dates = [log["created_at"] for log in data]
            assert dates == sorted(dates)
