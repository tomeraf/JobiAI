import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Literal

from app.database import get_db, AsyncSessionLocal
from app.models.job import Job, JobStatus, WorkflowStep
from app.models.contact import Contact
from app.models.activity import ActivityLog, ActionType
from app.models.site_selector import SiteSelector
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
    # Check for duplicate URL
    existing_result = await db.execute(select(Job).where(Job.url == job_data.url))
    existing_job = existing_result.scalar_one_or_none()
    if existing_job:
        raise HTTPException(
            status_code=409,
            detail=f"This URL has already been submitted (Job #{existing_job.id})"
        )

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
    Abort the currently running workflow and clear the queue.

    This will:
    1. Signal the LinkedIn client to stop
    2. Clear all queued jobs

    Note: The workflow orchestrator handles restoring the job's previous state
    when it catches the abort signal. We don't set status here to avoid race conditions.
    """
    client = LinkedInClient.get_instance()
    current_job_id = client.get_current_job()
    queued_jobs = client.get_queued_jobs()

    # Clear the queue
    for job_id in queued_jobs:
        client.remove_from_queue(job_id)

    if not current_job_id and not queued_jobs:
        return AbortResponse(
            success=False,
            message="No workflow is currently running or queued",
        )

    if current_job_id:
        # Request abort for running job - orchestrator will handle state restoration
        client.request_abort(current_job_id)

    return AbortResponse(
        success=True,
        message=f"Abort signal sent. Cleared {len(queued_jobs)} queued jobs.",
        job_id=current_job_id,
    )


@router.post("/abort/{job_id}", response_model=AbortResponse)
async def abort_specific_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """
    Abort a specific job - either currently running or queued.

    If the job is currently running, it sends an abort signal.
    If the job is queued, it removes it from the queue.

    Note: The workflow orchestrator handles restoring the job's previous state
    when it catches the abort signal. We don't set status here to avoid race conditions.
    """
    client = LinkedInClient.get_instance()
    current_job_id = client.get_current_job()
    queued_jobs = client.get_queued_jobs()

    # Check if this job is currently running
    if current_job_id == job_id:
        # Request abort - orchestrator will handle state restoration
        client.request_abort(job_id)
        return AbortResponse(
            success=True,
            message="Abort signal sent. Workflow will stop at next checkpoint.",
            job_id=job_id,
        )

    # Check if this job is queued
    if job_id in queued_jobs:
        client.remove_from_queue(job_id)
        return AbortResponse(
            success=True,
            message="Job removed from queue.",
            job_id=job_id,
        )

    return AbortResponse(
        success=False,
        message="Job is not running or queued.",
        job_id=job_id,
    )


@router.get("/current", response_model=dict)
async def get_current_job():
    """
    Get information about the currently running workflow and queued jobs.

    Returns:
        - is_running: True if a workflow is currently running
        - job_id: The ID of the currently running job (or null)
        - queued_jobs: List of job IDs waiting in queue
    """
    client = LinkedInClient.get_instance()
    current_job_id = client.get_current_job()
    queued_jobs = client.get_queued_jobs()

    return {
        "is_running": current_job_id is not None,
        "job_id": current_job_id,
        "queued_jobs": queued_jobs,
    }


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific job by ID."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


class ContactResponse(BaseModel):
    """Response for a contact."""
    id: int
    name: str
    linkedin_url: str
    company: str | None
    position: str | None
    message_sent_at: datetime | None
    reply_received_at: datetime | None

    class Config:
        from_attributes = True


class JobContactsResponse(BaseModel):
    """Response with contacts for a job."""
    job_id: int
    contacts: list[ContactResponse]
    total: int


@router.get("/{job_id}/contacts", response_model=JobContactsResponse)
async def get_job_contacts(job_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get contacts we messaged for a specific job.

    Only returns contacts that have been messaged (message_sent_at is not null).
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get contacts that were messaged for this job
    contacts_result = await db.execute(
        select(Contact)
        .where(Contact.job_id == job_id)
        .where(Contact.message_sent_at.isnot(None))
        .order_by(Contact.message_sent_at.desc())
    )
    contacts = contacts_result.scalars().all()

    return JobContactsResponse(
        job_id=job_id,
        contacts=contacts,
        total=len(contacts),
    )


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
    """
    Retry a failed or aborted job from where it left off.

    This will resume the workflow from the current workflow_step,
    preserving progress. If the job failed during company extraction,
    it will retry that. If it failed during the workflow, it will
    resume from the step where it stopped.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in [JobStatus.FAILED, JobStatus.ABORTED]:
        raise HTTPException(status_code=400, detail="Only failed or aborted jobs can be retried")

    # Clear error message
    job.error_message = None

    # Log retry with current step info
    activity = ActivityLog(
        action_type=ActionType.JOB_SUBMITTED,
        description=f"Job retry requested from step: {job.workflow_step.value}",
        details={"job_id": job_id, "workflow_step": job.workflow_step.value},
        job_id=job.id,
    )
    db.add(activity)

    # Add to queue so frontend knows this job is queued
    client = LinkedInClient.get_instance()
    client.add_to_queue(job_id)

    # Determine how to retry based on workflow_step
    if job.workflow_step == WorkflowStep.COMPANY_EXTRACTION or not job.company_name:
        # No company extracted yet - retry from company extraction
        job.status = JobStatus.PENDING
        job.processed_at = None
        await db.commit()
        background_tasks.add_task(process_job_task, job_id)
        return {"message": "Job queued for retry (company extraction)"}
    else:
        # Company already extracted - resume workflow from current step
        await db.commit()
        # Add to queue and run workflow - it will resume from current workflow_step
        client = LinkedInClient.get_instance()
        client.add_to_queue(job_id)
        background_tasks.add_task(run_workflow_task, job_id)
        return {"message": f"Job resuming from step: {job.workflow_step.value}"}


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
    force_search: bool = False  # Skip reply check and force a new search
    first_degree_only: bool = False  # Only search 1st degree (for checking accepted requests)


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


async def run_workflow_task(job_id: int, template_id: int | None = None, force_search: bool = False, first_degree_only: bool = False):
    """Background task to run the full workflow."""
    client = LinkedInClient.get_instance()

    # Wait for our turn - only one workflow can run at a time
    # Poll until no other job is running and we're first in queue
    while True:
        current_job = client.get_current_job()
        queued_jobs = client.get_queued_jobs()

        # Check if we were removed from the queue (user aborted this job)
        if job_id not in queued_jobs:
            logger.info(f"Job {job_id} was removed from queue, exiting")
            return

        # If no job is running and we're first in queue, we can start
        if current_job is None and queued_jobs and queued_jobs[0] == job_id:
            break

        # Wait a bit before checking again
        await asyncio.sleep(0.5)

    # Now it's our turn - remove from queue and set as current
    client.remove_from_queue(job_id)
    client.set_current_job(job_id)

    logger.info(f"Starting workflow task for job {job_id} (force_search={force_search}, first_degree_only={first_degree_only})")
    orchestrator = None
    try:
        async with AsyncSessionLocal() as db:
            try:
                orchestrator = WorkflowOrchestrator(db)
                result = await orchestrator.run_workflow(job_id, template_id, force_search=force_search, first_degree_only=first_degree_only)
                logger.info(f"Workflow result for job {job_id}: {result}")
                await db.commit()
            except Exception as e:
                logger.error(f"Workflow task failed for job {job_id}: {e}", exc_info=True)
                await db.rollback()
            finally:
                if orchestrator:
                    await orchestrator.close()
    finally:
        # Always clear current job when done, so next queued job can run
        client.set_current_job(None)
        client.clear_abort()  # Clear any abort signal for the next job


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
    force_search = workflow_data.force_search if workflow_data else False
    first_degree_only = workflow_data.first_degree_only if workflow_data else False

    # Add to queue so frontend knows this job is queued
    client = LinkedInClient.get_instance()
    client.add_to_queue(job_id)

    # Run workflow in background
    background_tasks.add_task(run_workflow_task, job_id, template_id, force_search, first_degree_only)

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

    # All names provided - update job state to show it's resuming
    # This ensures the UI shows normal state (white row) before workflow continues
    job.status = JobStatus.COMPLETED  # Set to COMPLETED, not PROCESSING - the background task will set PROCESSING
    job.pending_hebrew_names = None  # Clear pending names (translations are now saved)
    # Keep workflow_step as NEEDS_HEBREW_NAMES - the orchestrator will update it when it resumes

    await db.commit()  # Save the Hebrew names and updated job state

    # Add to queue and run workflow in background (will resume from NEEDS_HEBREW_NAMES step)
    client = LinkedInClient.get_instance()
    client.add_to_queue(job_id)
    background_tasks.add_task(run_workflow_task, job_id)

    # Refresh job to return updated state
    await db.refresh(job)

    return job


class UpdateCompanyRequest(BaseModel):
    """Request body for updating company name."""
    company_name: str


@router.put("/{job_id}/company", response_model=JobResponse)
async def update_company_name(
    job_id: int,
    data: UpdateCompanyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update the company name for a job.

    Use this when the bot extracted the wrong company name
    and you want to correct it manually. Also updates the site selector
    so future jobs from the same domain will use the new company name.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == JobStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="Cannot update a job that is currently processing")

    old_name = job.company_name
    new_name = data.company_name.strip()
    job.company_name = new_name

    # Also update the site selector for this domain so future jobs get the correct name
    from urllib.parse import urlparse
    try:
        parsed = urlparse(job.url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        if domain:
            selector_result = await db.execute(
                select(SiteSelector).where(SiteSelector.domain == domain)
            )
            selector = selector_result.scalar_one_or_none()

            if selector:
                selector.company_name = new_name
                selector.example_company = new_name
                logger.info(f"Updated site selector for domain '{domain}' with new company name: {new_name}")
    except Exception as e:
        logger.warning(f"Could not update site selector: {e}")

    # Log activity
    activity = ActivityLog(
        action_type=ActionType.COMPANY_EXTRACTED,
        description=f"Company name manually changed from '{old_name}' to '{new_name}'",
        details={"job_id": job_id, "old_name": old_name, "new_name": new_name},
        job_id=job.id,
    )
    db.add(activity)

    await db.commit()
    await db.refresh(job)

    logger.info(f"Updated company name for job {job_id}: '{old_name}' -> '{new_name}'")

    return job


@router.post("/{job_id}/reset", response_model=JobResponse)
async def reset_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Reset a job to start the workflow from scratch.

    This will:
    1. Delete all contacts associated with this job
    2. Reset workflow_step to COMPANY_EXTRACTION
    3. Reset status to COMPLETED (ready to run workflow)
    4. Keep the company_name (no need to re-extract)

    Use this when you want to start fresh - search for new connections
    and send messages again as if this job was just created.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == JobStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="Cannot reset a job that is currently processing")

    # Delete all contacts for this job
    contacts_result = await db.execute(select(Contact).where(Contact.job_id == job_id))
    contacts = contacts_result.scalars().all()
    for contact in contacts:
        await db.delete(contact)

    # Reset job state
    job.workflow_step = WorkflowStep.COMPANY_EXTRACTION
    job.status = JobStatus.COMPLETED  # Ready to run workflow
    job.error_message = None
    job.pending_hebrew_names = None
    job.last_reply_check_at = None

    # Log activity
    activity = ActivityLog(
        action_type=ActionType.JOB_SUBMITTED,
        description=f"Job reset - starting fresh for {job.company_name}",
        details={"job_id": job_id, "contacts_deleted": len(contacts)},
        job_id=job.id,
    )
    db.add(activity)

    await db.commit()
    await db.refresh(job)

    logger.info(f"Reset job {job_id}: deleted {len(contacts)} contacts, workflow reset to start")

    return job


@router.post("/{job_id}/find-more", response_model=JobResponse)
async def find_more_replies(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Continue searching for more people after someone replied.

    This will:
    1. Delete the contact(s) who replied
    2. Check if there are other contacts we messaged who haven't replied
    3. If yes: go to WAITING_FOR_REPLY (wait for those to reply)
    4. If no: go to SEARCH_CONNECTIONS (search for new people)

    Use this when someone replied but you want to find more people
    (e.g., the conversation didn't go well).
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == JobStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="Cannot modify a job that is currently processing")

    if job.workflow_step != WorkflowStep.DONE:
        raise HTTPException(
            status_code=400,
            detail="Job is not in DONE state - use this after someone replied"
        )

    # Find and delete contacts who replied
    replied_contacts_result = await db.execute(
        select(Contact)
        .where(Contact.job_id == job_id)
        .where(Contact.reply_received_at.isnot(None))
    )
    replied_contacts = replied_contacts_result.scalars().all()

    deleted_names = []
    for contact in replied_contacts:
        deleted_names.append(contact.name)
        await db.delete(contact)

    # Check if there are other contacts we messaged who haven't replied yet
    other_messaged_result = await db.execute(
        select(Contact)
        .where(Contact.job_id == job_id)
        .where(Contact.message_sent_at.isnot(None))
        .where(Contact.reply_received_at.is_(None))
    )
    other_messaged_contacts = other_messaged_result.scalars().all()

    if other_messaged_contacts:
        # There are other people we messaged - wait for their replies
        job.workflow_step = WorkflowStep.WAITING_FOR_REPLY
        next_step_msg = f"waiting for {len(other_messaged_contacts)} other contacts to reply"
    else:
        # No other contacts - search for new people
        job.workflow_step = WorkflowStep.SEARCH_CONNECTIONS
        next_step_msg = "searching for new contacts"

    job.status = JobStatus.COMPLETED  # Ready to run workflow

    # Log activity
    activity = ActivityLog(
        action_type=ActionType.CONNECTION_SEARCH,
        description=f"Removed {', '.join(deleted_names)} - {next_step_msg}",
        details={"job_id": job_id, "removed_contacts": deleted_names, "remaining_messaged": len(other_messaged_contacts)},
        job_id=job.id,
    )
    db.add(activity)

    await db.commit()
    await db.refresh(job)

    logger.info(f"Find more for job {job_id}: removed {len(deleted_names)} replied contacts, {next_step_msg}")

    # Always trigger workflow - if there are other contacts, it will check for replies
    # If no other contacts, it will search for new people
    client = LinkedInClient.get_instance()
    client.add_to_queue(job_id)
    background_tasks.add_task(run_workflow_task, job_id, None, True)  # force_search=True

    return job


@router.post("/{job_id}/contacts/{contact_id}/mark-replied")
async def mark_contact_replied(job_id: int, contact_id: int, db: AsyncSession = Depends(get_db)):
    """Mark a contact as replied, which completes the job workflow."""
    from datetime import datetime

    # Get the job
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get the contact
    result = await db.execute(
        select(Contact)
        .where(Contact.id == contact_id)
        .where(Contact.job_id == job_id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Mark the contact as replied
    contact.reply_received_at = datetime.utcnow()

    # Complete the job workflow
    job.workflow_step = WorkflowStep.DONE
    job.status = JobStatus.COMPLETED

    # Log activity
    activity = ActivityLog(
        action_type=ActionType.MESSAGE_SENT,
        description=f"Manually marked {contact.name} as replied - job complete!",
        details={"job_id": job_id, "contact_id": contact_id, "contact_name": contact.name},
        job_id=job.id,
    )
    db.add(activity)

    await db.commit()
    await db.refresh(job)
    await db.refresh(contact)

    logger.info(f"Manually marked contact {contact.name} as replied for job {job_id} - workflow complete")

    return {"success": True, "job": job, "contact": contact}


@router.delete("/{job_id}/contacts/{contact_id}")
async def delete_contact(job_id: int, contact_id: int, db: AsyncSession = Depends(get_db)):
    """Remove a contact from a job's contact list."""
    # Get the job
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get the contact
    result = await db.execute(
        select(Contact)
        .where(Contact.id == contact_id)
        .where(Contact.job_id == job_id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact_name = contact.name
    was_messaged = contact.message_sent_at is not None

    # Delete the contact
    await db.delete(contact)

    # Check if job should revert to waiting_for_accept
    # (when deleting the last messaged contact from a waiting_for_reply job)
    workflow_changed = False
    if job.workflow_step == WorkflowStep.WAITING_FOR_REPLY and was_messaged:
        # Count remaining messaged contacts (excluding the one being deleted)
        result = await db.execute(
            select(func.count(Contact.id))
            .where(Contact.job_id == job_id)
            .where(Contact.id != contact_id)
            .where(Contact.message_sent_at.isnot(None))
        )
        remaining_messaged = result.scalar() or 0

        if remaining_messaged == 0:
            # No more messaged contacts, revert to waiting_for_accept
            job.workflow_step = WorkflowStep.WAITING_FOR_ACCEPT
            workflow_changed = True
            logger.info(f"Job {job_id}: No more messaged contacts, reverting to waiting_for_accept")

    # Log activity
    activity = ActivityLog(
        action_type=ActionType.CONNECTION_SEARCH,
        description=f"Removed {contact_name} from contact list",
        details={
            "job_id": job_id,
            "contact_id": contact_id,
            "contact_name": contact_name,
            "workflow_changed": workflow_changed
        },
        job_id=job.id,
    )
    db.add(activity)

    await db.commit()

    logger.info(f"Removed contact {contact_name} from job {job_id}")

    return {"success": True, "message": f"Contact {contact_name} removed", "workflow_changed": workflow_changed}


@router.post("/{job_id}/mark-done", response_model=JobResponse)
async def mark_job_done(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a job as successfully done (user got the job or positive outcome).

    This will:
    1. Set status to DONE
    2. Set workflow_step to DONE
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == JobStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="Cannot mark a processing job as done")

    job.status = JobStatus.DONE
    job.workflow_step = WorkflowStep.DONE

    # Log activity
    activity = ActivityLog(
        action_type=ActionType.JOB_SUBMITTED,
        description=f"Job marked as done - success!",
        details={"job_id": job_id, "company": job.company_name},
        job_id=job.id,
    )
    db.add(activity)

    await db.commit()
    await db.refresh(job)

    logger.info(f"Job {job_id} marked as done by user")

    return job


@router.post("/{job_id}/mark-rejected", response_model=JobResponse)
async def mark_job_rejected(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a job as rejected (user not interested or negative outcome).

    This will:
    1. Set status to REJECTED
    2. Set workflow_step to DONE
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == JobStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="Cannot mark a processing job as rejected")

    job.status = JobStatus.REJECTED
    job.workflow_step = WorkflowStep.DONE

    # Log activity
    activity = ActivityLog(
        action_type=ActionType.JOB_SUBMITTED,
        description=f"Job marked as rejected",
        details={"job_id": job_id, "company": job.company_name},
        job_id=job.id,
    )
    db.add(activity)

    await db.commit()
    await db.refresh(job)

    logger.info(f"Job {job_id} marked as rejected by user")

    return job


class UpdateWorkflowStepRequest(BaseModel):
    """Request body for updating workflow step."""
    workflow_step: str
    status: str | None = None  # Optional - also update status


@router.put("/{job_id}/workflow-step", response_model=JobResponse)
async def update_workflow_step(
    job_id: int,
    data: UpdateWorkflowStepRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually update the workflow step for a job.

    This is useful for correcting the workflow state or skipping steps.
    Optionally also updates the status.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == JobStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="Cannot update a job that is currently processing")

    # Validate workflow step
    try:
        new_step = WorkflowStep(data.workflow_step)
    except ValueError:
        valid_steps = [s.value for s in WorkflowStep]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid workflow step: {data.workflow_step}. Valid values: {valid_steps}"
        )

    old_step = job.workflow_step
    old_status = job.status
    job.workflow_step = new_step

    # Optionally update status
    if data.status:
        try:
            new_status = JobStatus(data.status)
            job.status = new_status
        except ValueError:
            valid_statuses = [s.value for s in JobStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {data.status}. Valid values: {valid_statuses}"
            )

    # Clear error message when manually changing state
    job.error_message = None

    # Log activity
    activity = ActivityLog(
        action_type=ActionType.JOB_SUBMITTED,
        description=f"Workflow step manually changed from '{old_step.value}' to '{new_step.value}'",
        details={
            "job_id": job_id,
            "old_step": old_step.value,
            "new_step": new_step.value,
            "old_status": old_status.value,
            "new_status": job.status.value,
        },
        job_id=job.id,
    )
    db.add(activity)

    await db.commit()
    await db.refresh(job)

    logger.info(f"Job {job_id} workflow step manually changed: {old_step.value} -> {new_step.value}")

    return job
