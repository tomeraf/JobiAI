from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Literal

from app.database import get_db, AsyncSessionLocal
from app.models.job import Job, JobStatus, WorkflowStep
from app.models.activity import ActivityLog, ActionType
from app.services.job_processor import JobProcessor
from app.services.workflow_orchestrator import WorkflowOrchestrator
from app.services.hebrew_names import save_hebrew_name
from app.services.linkedin.client import LinkedInClient
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class JobCreate(BaseModel):
    url: str


class JobResponse(BaseModel):
    id: int
    url: str
    company_name: str | None
    job_title: str | None
    status: str
    workflow_step: str
    error_message: str | None
    pending_hebrew_names: list[str] | None = None
    created_at: datetime
    processed_at: datetime | None

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int


class CompanySubmit(BaseModel):
    """Submit company info for a job that needs user input."""
    company_name: str
    site_type: Literal["company", "platform"] = "company"  # Type of site
    platform_name: str | None = None  # Required if site_type is "platform"
    company_selector: str | None = None  # Legacy field, not used


async def process_job_task(job_id: int):
    """Background task to process a job."""
    async with AsyncSessionLocal() as db:
        try:
            processor = JobProcessor(db)
            await processor.process_job(job_id)
            await db.commit()
        except Exception as e:
            logger.error(f"Background task failed for job {job_id}: {e}")
            await db.rollback()


@router.post("", response_model=JobResponse)
async def create_job(
    job_data: JobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Submit a new job URL for processing."""
    # Create job
    job = Job(url=job_data.url, status=JobStatus.PENDING)
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # Log activity
    activity = ActivityLog(
        action_type=ActionType.JOB_SUBMITTED,
        description=f"Job URL submitted: {job_data.url}",
        details={"url": job_data.url},
        job_id=job.id,
    )
    db.add(activity)

    logger.info(f"Created job {job.id} for URL: {job_data.url}")

    # Store job_id before returning (db will be committed after return)
    job_id = job.id

    # Add background task to process job
    background_tasks.add_task(process_job_task, job_id)

    return job


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all jobs with optional status filter."""
    query = select(Job).order_by(Job.created_at.desc())

    if status:
        try:
            status_enum = JobStatus(status)
            query = query.where(Job.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    # Get total count
    count_result = await db.execute(select(Job))
    total = len(count_result.scalars().all())

    # Get paginated results
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    jobs = result.scalars().all()

    return JobListResponse(jobs=jobs, total=total)


# NOTE: These routes MUST be before /{job_id} routes to avoid matching conflicts
class AbortResponse(BaseModel):
    """Response from abort request."""
    success: bool
    message: str
    job_id: int | None = None


@router.post("/abort", response_model=AbortResponse)
async def abort_workflow(db: AsyncSession = Depends(get_db)):
    """
    Abort the currently running workflow.

    This will:
    1. Signal the LinkedIn client to stop
    2. Set the job status to ABORTED
    3. Close the browser
    """
    client = LinkedInClient.get_instance()
    current_job_id = client.get_current_job()

    if not current_job_id:
        return AbortResponse(
            success=False,
            message="No workflow is currently running",
        )

    # Request abort
    client.request_abort(current_job_id)

    # Update job status immediately
    result = await db.execute(select(Job).where(Job.id == current_job_id))
    job = result.scalar_one_or_none()

    if job:
        job.status = JobStatus.ABORTED
        job.error_message = "Workflow aborted by user"
        await db.commit()

    return AbortResponse(
        success=True,
        message="Abort signal sent. Workflow will stop at next checkpoint.",
        job_id=current_job_id,
    )


@router.get("/current", response_model=dict)
async def get_current_job():
    """
    Get information about the currently running workflow.

    Returns the job ID if a workflow is running, or null if not.
    """
    client = LinkedInClient.get_instance()
    current_job_id = client.get_current_job()

    return {
        "is_running": current_job_id is not None,
        "job_id": current_job_id,
    }


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific job by ID."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.delete("/{job_id}")
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a job."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    await db.delete(job)
    return {"message": "Job deleted"}


@router.post("/{job_id}/retry")
async def retry_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed job."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried")

    job.status = JobStatus.PENDING
    job.error_message = None
    job.processed_at = None

    # Log retry
    activity = ActivityLog(
        action_type=ActionType.JOB_SUBMITTED,
        description=f"Job retry requested",
        details={"job_id": job_id},
        job_id=job.id,
    )
    db.add(activity)

    # Add background task to process job
    background_tasks.add_task(process_job_task, job_id)

    return {"message": "Job queued for retry"}


@router.post("/{job_id}/company", response_model=JobResponse)
async def submit_company(
    job_id: int,
    company_data: CompanySubmit,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit company info for a job that needs user input.

    This is called when the bot doesn't recognize the job site domain
    and needs the user to provide information about the site.

    Parameters:
        - company_name: The name of the company for this job
        - site_type: "company" for a company's career page, "platform" for job platforms
        - platform_name: Name of the platform (required if site_type is "platform")

    The system will learn from this input and recognize similar URLs in the future.
    """
    # Validate platform_name is provided for platform type
    if company_data.site_type == "platform" and not company_data.platform_name:
        raise HTTPException(
            status_code=400,
            detail="platform_name is required when site_type is 'platform'"
        )

    processor = JobProcessor(db)
    result = await processor.submit_company_info(
        job_id=job_id,
        company_name=company_data.company_name,
        site_type=company_data.site_type,
        platform_name=company_data.platform_name,
    )

    if not result["success"]:
        # Check if it's a not found error
        if "not found" in result["message"].lower():
            raise HTTPException(status_code=404, detail=result["message"])
        raise HTTPException(status_code=400, detail=result["message"])

    # Fetch and return updated job
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.post("/{job_id}/process")
async def trigger_process(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger processing for a job.

    Useful for re-processing jobs that are stuck or for testing.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == JobStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="Job is already being processed")

    # Reset to pending
    job.status = JobStatus.PENDING
    job.error_message = None

    background_tasks.add_task(process_job_task, job_id)

    return {"message": "Job processing triggered"}


class WorkflowTrigger(BaseModel):
    """Request body for triggering the full workflow."""
    template_id: int | None = None


class WorkflowResponse(BaseModel):
    """Response from workflow execution."""
    success: bool
    job_id: int
    company: str | None = None
    connections_found: int = 0
    messages_sent: int = 0
    connection_requests_sent: int = 0
    steps_completed: list[str] = []
    error: str | None = None


async def run_workflow_task(job_id: int, template_id: int | None = None):
    """Background task to run the full workflow."""
    logger.info(f"Starting workflow task for job {job_id}")
    orchestrator = None
    async with AsyncSessionLocal() as db:
        try:
            orchestrator = WorkflowOrchestrator(db)
            result = await orchestrator.run_workflow(job_id, template_id)
            logger.info(f"Workflow result for job {job_id}: {result}")
            await db.commit()
        except Exception as e:
            logger.error(f"Workflow task failed for job {job_id}: {e}", exc_info=True)
            await db.rollback()
        finally:
            if orchestrator:
                await orchestrator.close()


@router.post("/{job_id}/workflow", response_model=WorkflowResponse)
async def trigger_workflow(
    job_id: int,
    workflow_data: WorkflowTrigger | None = None,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger the full LinkedIn workflow for a job.

    This will:
    1. Search for existing connections at the company
    2. If found: Send personalized messages
    3. If not found: Search LinkedIn for people at the company
    4. Send connection requests to found people

    Prerequisites:
    - Job must have company_name extracted (status = COMPLETED after company extraction)
    - Must be logged into LinkedIn

    Parameters:
    - template_id: Optional message template ID (uses default if not provided)
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.company_name:
        raise HTTPException(
            status_code=400,
            detail="Company name not extracted yet. Process the job first."
        )

    if job.status == JobStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="Job is already being processed")

    if job.workflow_step == WorkflowStep.DONE:
        raise HTTPException(
            status_code=400,
            detail="Workflow already completed for this job"
        )

    template_id = workflow_data.template_id if workflow_data else None

    # Run workflow in background
    background_tasks.add_task(run_workflow_task, job_id, template_id)

    return WorkflowResponse(
        success=True,
        job_id=job_id,
        company=job.company_name,
        steps_completed=["workflow_queued"],
    )


@router.post("/{job_id}/search-connections")
async def search_connections(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Search for existing LinkedIn connections at the company.

    This is Step 2 of the workflow, executed manually.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.company_name:
        raise HTTPException(
            status_code=400,
            detail="Company name not extracted yet"
        )

    orchestrator = WorkflowOrchestrator(db)
    try:
        await orchestrator.initialize_browser()

        # Search connections
        connections = await orchestrator.search.search_connections_by_company(
            job.company_name
        )

        # Save contacts if found
        saved = []
        if connections:
            saved = await orchestrator._save_contacts(job, connections, is_connection=True)

        # Log activity
        await orchestrator._log_activity(
            ActionType.CONNECTION_SEARCH,
            f"Manual search: {len(connections)} connections at {job.company_name}",
            {"company": job.company_name, "results_count": len(connections)},
            job_id=job.id,
        )

        await db.commit()

        return {
            "success": True,
            "company": job.company_name,
            "connections_found": len(connections),
            "contacts_saved": len(saved),
            "connections": [
                {"name": c.get("name"), "linkedin_url": c.get("linkedin_url")}
                for c in connections
            ],
        }

    except Exception as e:
        logger.error(f"Search connections failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        await orchestrator.close()


class HebrewNameInput(BaseModel):
    """Single Hebrew name translation input."""
    english_name: str
    hebrew_name: str


class HebrewNamesSubmit(BaseModel):
    """Submit Hebrew name translations for a paused job."""
    names: list[HebrewNameInput]


class PendingNamesResponse(BaseModel):
    """Response with pending Hebrew names for a job."""
    job_id: int
    workflow_step: str
    pending_names: list[str]


@router.get("/{job_id}/pending-hebrew-names", response_model=PendingNamesResponse)
async def get_pending_hebrew_names(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the list of names that need Hebrew translations for a paused job.

    When a job is in NEEDS_HEBREW_NAMES state, this returns the list of
    English names that need to be translated to Hebrew before the workflow
    can continue.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    pending = job.pending_hebrew_names or []

    return PendingNamesResponse(
        job_id=job.id,
        workflow_step=job.workflow_step.value,
        pending_names=pending,
    )


@router.post("/{job_id}/hebrew-names", response_model=JobResponse)
async def submit_hebrew_names(
    job_id: int,
    names_data: HebrewNamesSubmit,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit Hebrew name translations and resume the workflow.

    After providing translations for all pending names, the workflow will
    automatically resume and send messages using the Hebrew names.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.workflow_step != WorkflowStep.NEEDS_HEBREW_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not waiting for Hebrew names (current step: {job.workflow_step.value})"
        )

    if not names_data.names:
        raise HTTPException(status_code=400, detail="No names provided")

    # Save all provided Hebrew name translations
    for name_input in names_data.names:
        if name_input.english_name and name_input.hebrew_name:
            await save_hebrew_name(
                english_name=name_input.english_name,
                hebrew_name=name_input.hebrew_name,
                db=db,
            )

    # Check if all pending names are now translated
    pending = job.pending_hebrew_names or []
    provided_names = {n.english_name.lower() for n in names_data.names}

    missing = [name for name in pending if name.lower() not in provided_names]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing translations for: {', '.join(missing)}"
        )

    # All names provided - resume workflow
    await db.commit()  # Save the Hebrew names first

    # Run workflow in background (will resume from NEEDS_HEBREW_NAMES step)
    background_tasks.add_task(run_workflow_task, job_id)

    # Refresh job to return updated state
    await db.refresh(job)

    return job
