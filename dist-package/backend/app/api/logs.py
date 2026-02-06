from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.activity import ActivityLog, ActionType
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class LogResponse(BaseModel):
    id: int
    action_type: str
    description: str
    details: dict | None
    job_id: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class LogListResponse(BaseModel):
    logs: list[LogResponse]
    total: int


class LogStats(BaseModel):
    total_actions: int
    jobs_submitted: int
    messages_sent: int
    connections_requested: int
    errors: int


@router.get("", response_model=LogListResponse)
async def list_logs(
    action_type: str | None = None,
    job_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List activity logs with optional filters."""
    query = select(ActivityLog).order_by(ActivityLog.created_at.desc())

    if action_type:
        try:
            action_enum = ActionType(action_type)
            query = query.where(ActivityLog.action_type == action_enum)
        except ValueError:
            pass  # Ignore invalid action types

    if job_id:
        query = query.where(ActivityLog.job_id == job_id)

    # Get total count
    count_query = select(func.count(ActivityLog.id))
    if action_type:
        try:
            action_enum = ActionType(action_type)
            count_query = count_query.where(ActivityLog.action_type == action_enum)
        except ValueError:
            pass
    if job_id:
        count_query = count_query.where(ActivityLog.job_id == job_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get paginated results
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return LogListResponse(logs=logs, total=total)


@router.get("/stats", response_model=LogStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get activity statistics."""
    # Total actions
    total_result = await db.execute(select(func.count(ActivityLog.id)))
    total = total_result.scalar() or 0

    # Jobs submitted
    jobs_result = await db.execute(
        select(func.count(ActivityLog.id)).where(
            ActivityLog.action_type == ActionType.JOB_SUBMITTED
        )
    )
    jobs_submitted = jobs_result.scalar() or 0

    # Messages sent
    messages_result = await db.execute(
        select(func.count(ActivityLog.id)).where(
            ActivityLog.action_type == ActionType.MESSAGE_SENT
        )
    )
    messages_sent = messages_result.scalar() or 0

    # Connections requested
    connections_result = await db.execute(
        select(func.count(ActivityLog.id)).where(
            ActivityLog.action_type == ActionType.CONNECTION_REQUEST_SENT
        )
    )
    connections_requested = connections_result.scalar() or 0

    # Errors
    errors_result = await db.execute(
        select(func.count(ActivityLog.id)).where(
            ActivityLog.action_type == ActionType.ERROR
        )
    )
    errors = errors_result.scalar() or 0

    return LogStats(
        total_actions=total,
        jobs_submitted=jobs_submitted,
        messages_sent=messages_sent,
        connections_requested=connections_requested,
        errors=errors,
    )


@router.get("/recent", response_model=list[LogResponse])
async def get_recent_logs(
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get most recent activity logs."""
    result = await db.execute(
        select(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/job/{job_id}", response_model=list[LogResponse])
async def get_job_logs(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get all logs for a specific job."""
    result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.job_id == job_id)
        .order_by(ActivityLog.created_at.asc())
    )
    return result.scalars().all()
