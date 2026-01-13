"""
Workflow orchestrator that runs the full job processing pipeline.

Flow:
1. Extract company name from job URL (handled by JobProcessor)
2. Search existing LinkedIn connections for people at that company
3. If connections found: Send personalized messages
4. If no connections: Search LinkedIn for people at company
5. Send connection requests to found people
6. Log all activities
"""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus, WorkflowStep
from app.models.contact import Contact
from app.models.template import Template
from app.models.activity import ActivityLog, ActionType
from app.services.linkedin.client import LinkedInClient, WorkflowAbortedException, MissingHebrewNamesException
from app.services.hebrew_names import (
    translate_name_to_hebrew,
    translate_name_to_hebrew_sync,
    is_hebrew_text,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowOrchestrator:
    """Orchestrates the full job workflow after company extraction."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.client: LinkedInClient | None = None

    def initialize_services(self):
        """Initialize LinkedIn client singleton."""
        self.client = LinkedInClient.get_instance()

    async def run_workflow(self, job_id: int, template_id: int | None = None, force_search: bool = False, first_degree_only: bool = False) -> dict:
        """
        Run the full workflow for a job.

        Args:
            job_id: The job to process
            template_id: Optional template ID (uses default if not provided)
            force_search: If True, skip reply checking and go straight to searching
            first_degree_only: If True, only search for 1st degree (for checking accepted connection requests)

        Returns:
            Dict with workflow results
        """
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            return {"success": False, "error": f"Job {job_id} not found"}

        if not job.company_name:
            return {"success": False, "error": "Company name not extracted yet"}

        # Get template
        template = await self._get_template(template_id)
        if not template:
            return {"success": False, "error": "No message template found"}

        # Store previous state to restore on abort
        previous_status = job.status
        previous_workflow_step = job.workflow_step

        try:
            # Initialize services
            logger.info(f"Initializing workflow services for job {job_id}")
            self.initialize_services()

            # Set current job and clear any previous abort flag
            self.client.clear_abort()
            self.client.set_current_job(job_id)

            # Update status and clear any previous error
            job.status = JobStatus.PROCESSING
            job.error_message = None  # Clear previous error when starting new workflow
            logger.info(f"Job {job_id} status set to PROCESSING, starting workflow")

            # Run workflow steps based on current step
            workflow_result = await self._run_from_step(job, template, force_search=force_search, first_degree_only=first_degree_only)
            logger.info(f"Workflow completed for job {job_id}: {workflow_result}")

            return workflow_result

        except WorkflowAbortedException:
            logger.info(f"Workflow aborted by user for job {job_id}, restoring previous state")
            # Restore previous state and workflow step (no error message - user intentionally aborted)
            job.status = previous_status
            job.workflow_step = previous_workflow_step
            job.error_message = None  # Clear any previous error message

            return {"success": False, "error": "Workflow aborted by user", "aborted": True}

        except Exception as e:
            logger.error(f"Workflow error for job {job_id}: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)

            await self._log_activity(
                ActionType.ERROR,
                f"Workflow failed: {e}",
                {"job_id": job_id, "error": str(e)},
                job_id=job.id,
            )

            return {"success": False, "error": str(e)}

        finally:
            # Clear current job
            self.client.set_current_job(None)

    async def _run_from_step(self, job: Job, template: Template, force_search: bool = False, first_degree_only: bool = False) -> dict:
        """Run workflow from the current step."""
        results = {
            "success": True,
            "job_id": job.id,
            "company": job.company_name,
            "connections_found": 0,
            "messages_sent": 0,
            "connection_requests_sent": 0,
            "steps_completed": [],
        }

        company = job.company_name

        # Check for abort before starting
        self.client.check_abort()

        # Guard: Don't run workflow for already completed jobs
        if job.workflow_step == WorkflowStep.DONE:
            logger.warning(f"Job {job.id} is already at DONE step, nothing to do")
            job.status = JobStatus.COMPLETED
            return results

        # Resume from NEEDS_HEBREW_NAMES step - now that user provided translations,
        # re-run the search WITH message generator to send messages
        if job.workflow_step == WorkflowStep.NEEDS_HEBREW_NAMES:
            logger.info(f"Resuming workflow for job {job.id} - sending messages with Hebrew names")
            job.pending_hebrew_names = None
            job.workflow_step = WorkflowStep.MESSAGE_CONNECTIONS
            await self.db.flush()

            # Get template for message generation
            template_has_hebrew = is_hebrew_text(template.content or "")

            # Create message generator with Hebrew translation
            def create_message(name: str, company_name: str) -> str:
                """Generate message text using the template with Hebrew names."""
                first_name = name.split()[0] if name else ""
                if template_has_hebrew:
                    translated = translate_name_to_hebrew_sync(first_name)
                    if translated:
                        first_name = translated
                    else:
                        # Hebrew translation needed but not available - raise exception
                        raise MissingHebrewNamesException(
                            missing_names=[first_name],
                            first_degree_found=[]
                        )
                return template.format_message(name=first_name, company=company_name)

            # Re-run search with message generator to send messages
            try:
                search_results = await self.client.search_company_all_degrees(
                    company, limit=15, message_generator=create_message
                )
            except MissingHebrewNamesException as e:
                # Another Hebrew name translation missing - pause workflow for user input
                logger.info(f"Missing Hebrew translation for: {e.missing_names}")

                job.workflow_step = WorkflowStep.NEEDS_HEBREW_NAMES
                job.status = JobStatus.NEEDS_INPUT
                job.pending_hebrew_names = e.missing_names

                await self._log_activity(
                    ActionType.COMPANY_INPUT_NEEDED,
                    f"Hebrew name translation needed for: {e.missing_names[0]}",
                    {"missing_names": e.missing_names, "company": company},
                    job_id=job.id,
                )

                await self.db.flush()

                results["steps_completed"].append("message_connections")
                results["needs_hebrew_names"] = e.missing_names
                results["success"] = True  # Not a failure, just paused

                return results

            messages_sent = search_results.get("messages_sent", [])
            second_degree = search_results.get("second_degree", [])
            third_plus = search_results.get("third_plus", [])

            if messages_sent:
                logger.info(f"Sent {len(messages_sent)} messages after Hebrew name input")

                # Save messaged contacts
                saved_contacts = await self._save_contacts(
                    job, messages_sent, is_connection=True, already_messaged=True
                )

                for contact in saved_contacts:
                    await self._log_activity(
                        ActionType.MESSAGE_SENT,
                        f"Message sent to {contact.name}",
                        {"contact_id": contact.id, "name": contact.name},
                        job_id=job.id,
                    )

                job.workflow_step = WorkflowStep.WAITING_FOR_REPLY
                job.status = JobStatus.COMPLETED
                results["messages_sent"] = len(messages_sent)
                results["steps_completed"].append("message_connections")
                return results

            elif second_degree or third_plus:
                # No 1st degree could be messaged, but we got 2nd/3rd degree
                people = second_degree or third_plus
                degree_type = "2nd" if second_degree else "3rd+"

                logger.info(f"No 1st degree messages sent, connected with {len(people)} {degree_type} degree")

                for person in people:
                    await self._log_activity(
                        ActionType.CONNECTION_REQUEST_SENT,
                        f"Connection request sent to {person.get('name', 'Unknown')}",
                        {"name": person.get("name"), "linkedin_url": person.get("linkedin_url")},
                        job_id=job.id,
                    )

                job.workflow_step = WorkflowStep.WAITING_FOR_ACCEPT
                job.status = JobStatus.COMPLETED
                results["connection_requests_sent"] = len(people)
                results["steps_completed"].append("send_requests")
                return results

            else:
                # Nothing worked
                job.workflow_step = WorkflowStep.DONE
                job.status = JobStatus.FAILED
                job.error_message = "Could not send any messages or connection requests"
                results["success"] = False
                results["error"] = job.error_message
                return results

        # Resume from WAITING_FOR_REPLY - check if anyone replied (unless force_search)
        if job.workflow_step == WorkflowStep.WAITING_FOR_REPLY:
            if force_search:
                # User wants to search for more candidates, skip reply check
                logger.info(f"Force search requested for job {job.id} - skipping reply check")
                job.workflow_step = WorkflowStep.SEARCH_CONNECTIONS
                await self.db.flush()
                # Fall through to run the normal search flow below
            else:
                logger.info(f"Checking for replies for job {job.id}")
                reply_result = await self._check_for_replies(job)
                # Always update the last reply check timestamp
                job.last_reply_check_at = datetime.utcnow()
                if reply_result.get("reply_received"):
                    # Got a reply! Job is done!
                    job.workflow_step = WorkflowStep.DONE
                    job.status = JobStatus.COMPLETED
                    job.processed_at = datetime.utcnow()
                    results["success"] = True
                    results["steps_completed"].append("reply_received")
                    return results
                elif reply_result.get("check_failed"):
                    # Some contacts couldn't be checked - show error to user
                    job.status = JobStatus.COMPLETED  # Not failed, just couldn't check
                    job.error_message = reply_result.get("error", "Could not check some conversations")
                    results["success"] = False
                    results["error"] = job.error_message
                    results["steps_completed"].append("check_replies_failed")
                    return results
                else:
                    # No reply yet - stay in waiting state
                    job.status = JobStatus.COMPLETED  # Not failed, just waiting
                    results["success"] = True
                    results["steps_completed"].append("checked_replies_none_yet")
                    return results

        # Resume from WAITING_FOR_ACCEPT - search for new 1st degree connections
        if job.workflow_step == WorkflowStep.WAITING_FOR_ACCEPT:
            logger.info(f"Checking for new 1st degree connections for job {job.id}")
            # Re-run search to find if any connection requests were accepted
            job.workflow_step = WorkflowStep.SEARCH_CONNECTIONS
            await self.db.flush()
            # Fall through to run the normal search flow below

        # Resume from intermediate steps that failed - restart search from scratch
        # These steps can fail due to network issues, rate limits, etc.
        if job.workflow_step in [WorkflowStep.MESSAGE_CONNECTIONS, WorkflowStep.SEARCH_LINKEDIN, WorkflowStep.SEND_REQUESTS]:
            logger.info(f"Resuming from failed step {job.workflow_step.value} - restarting search for job {job.id}")
            job.workflow_step = WorkflowStep.SEARCH_CONNECTIONS
            await self.db.flush()
            # Fall through to run the normal search flow below

        # Combined search: 1st degree first, then 2nd degree, then 3rd+ if needed
        # All in a single browser session
        if job.workflow_step in [WorkflowStep.COMPANY_EXTRACTION, WorkflowStep.SEARCH_CONNECTIONS]:
            job.workflow_step = WorkflowStep.SEARCH_CONNECTIONS
            await self.db.flush()

            logger.info(f"Starting combined search at {company}")

            # Check if template contains Hebrew text (to decide if we need Hebrew names)
            template_has_hebrew = is_hebrew_text(template.content or "")

            # Create message generator with Hebrew translation
            # This will raise MissingHebrewNamesException if translation is needed but missing
            def create_message(name: str, company_name: str) -> str:
                """Generate message text using the template with Hebrew names."""
                first_name = name.split()[0] if name else ""
                if template_has_hebrew:
                    translated = translate_name_to_hebrew_sync(first_name)
                    if translated:
                        first_name = translated
                    else:
                        # Hebrew translation needed but not available - raise exception
                        raise MissingHebrewNamesException(
                            missing_names=[first_name],
                            first_degree_found=[]
                        )
                return template.format_message(name=first_name, company=company_name)

            try:
                # Run search with message generator - will raise exception if Hebrew name missing
                search_results = await self.client.search_company_all_degrees(
                    company, limit=15, message_generator=create_message, first_degree_only=first_degree_only
                )
            except MissingHebrewNamesException as e:
                # Hebrew name translation missing - pause workflow for user input
                logger.info(f"Missing Hebrew translation for: {e.missing_names}")

                job.workflow_step = WorkflowStep.NEEDS_HEBREW_NAMES
                job.status = JobStatus.NEEDS_INPUT
                job.pending_hebrew_names = e.missing_names

                await self._log_activity(
                    ActionType.COMPANY_INPUT_NEEDED,
                    f"Hebrew name translation needed for: {e.missing_names[0]}",
                    {"missing_names": e.missing_names, "company": company},
                    job_id=job.id,
                )

                await self.db.flush()

                results["steps_completed"].append("search_connections")
                results["needs_hebrew_names"] = e.missing_names
                results["success"] = True  # Not a failure, just paused

                return results

            first_degree = search_results.get("first_degree", [])
            second_degree = search_results.get("second_degree", [])
            third_plus = search_results.get("third_plus", [])

            await self._log_activity(
                ActionType.CONNECTION_SEARCH,
                f"Searched connections at {company}",
                {
                    "company": company,
                    "first_degree_count": len(first_degree),
                    "second_degree_count": len(second_degree),
                    "third_plus_count": len(third_plus),
                },
                job_id=job.id,
            )

            if first_degree:
                # Save 1st degree contacts to database
                saved_contacts = await self._save_contacts(job, first_degree, is_connection=True)
                results["connections_found"] = len(saved_contacts)
                results["steps_completed"].append("search_connections")

                # Log found connections
                for contact in saved_contacts:
                    await self._log_activity(
                        ActionType.CONNECTION_FOUND,
                        f"Found connection: {contact.name}",
                        {"contact_id": contact.id, "name": contact.name},
                        job_id=job.id,
                    )

                # Check if messages were sent from the search page
                messages_sent_from_search = search_results.get("messages_sent", [])
                if messages_sent_from_search:
                    # Messages were already sent directly from search page
                    logger.info(f"Messages already sent to {len(messages_sent_from_search)} people from search page")
                    results["messages_sent"] = len(messages_sent_from_search)
                    results["steps_completed"].append("message_connections")

                    # Save the messaged contacts to the database
                    saved_messaged_contacts = await self._save_contacts(
                        job, messages_sent_from_search, is_connection=True, already_messaged=True
                    )
                    logger.info(f"Saved {len(saved_messaged_contacts)} messaged contacts to database")

                    # Log each message sent
                    for contact in saved_messaged_contacts:
                        await self._log_activity(
                            ActionType.MESSAGE_SENT,
                            f"Message sent to {contact.name}",
                            {"contact_id": contact.id, "name": contact.name, "linkedin_url": contact.linkedin_url},
                            job_id=job.id,
                        )

                    # Now waiting for a reply
                    job.workflow_step = WorkflowStep.WAITING_FOR_REPLY
                    job.status = JobStatus.COMPLETED  # Completed this phase, but waiting

                elif second_degree:
                    # All 1st degree were skipped (existing history), but we connected with 2nd degree
                    logger.info(f"All {len(first_degree)} 1st degree connections were skipped (existing history)")
                    logger.info(f"Sent connection requests to {len(second_degree)} 2nd degree people instead")

                    await self._log_activity(
                        ActionType.LINKEDIN_SEARCH,
                        f"1st degree connections skipped (existing history), connected with 2nd degree at {company}",
                        {"company": company, "first_degree_skipped": len(first_degree), "second_degree_connected": len(second_degree)},
                        job_id=job.id,
                    )

                    # Don't save 2nd degree contacts - they'll become 1st degree when they accept
                    # and we'll save them when we message them
                    results["steps_completed"].append("search_linkedin")
                    results["connection_requests_sent"] = len(second_degree)
                    results["steps_completed"].append("send_requests")

                    # Log connection requests sent (without saving contacts)
                    for person in second_degree:
                        await self._log_activity(
                            ActionType.CONNECTION_REQUEST_SENT,
                            f"Connection request sent to {person.get('name', 'Unknown')}",
                            {"name": person.get("name"), "linkedin_url": person.get("linkedin_url")},
                            job_id=job.id,
                        )

                    # Now waiting for connection accepts
                    job.workflow_step = WorkflowStep.WAITING_FOR_ACCEPT
                    job.status = JobStatus.COMPLETED  # Completed this phase, but waiting

                elif third_plus:
                    # All 1st degree were skipped, no 2nd degree, but we connected with 3rd+
                    logger.info(f"All {len(first_degree)} 1st degree connections were skipped (existing history)")
                    logger.info(f"Sent connection requests to {len(third_plus)} 3rd+ degree people instead")

                    await self._log_activity(
                        ActionType.LINKEDIN_SEARCH,
                        f"1st degree connections skipped (existing history), connected with 3rd+ degree at {company}",
                        {"company": company, "first_degree_skipped": len(first_degree), "third_plus_connected": len(third_plus)},
                        job_id=job.id,
                    )

                    # Don't save 3rd+ degree contacts - they'll become 1st degree when they accept
                    # and we'll save them when we message them
                    results["steps_completed"].append("search_linkedin")
                    results["connection_requests_sent"] = len(third_plus)
                    results["steps_completed"].append("send_requests")

                    # Log connection requests sent (without saving contacts)
                    for person in third_plus:
                        await self._log_activity(
                            ActionType.CONNECTION_REQUEST_SENT,
                            f"Connection request sent to {person.get('name', 'Unknown')}",
                            {"name": person.get("name"), "linkedin_url": person.get("linkedin_url")},
                            job_id=job.id,
                        )

                    # Now waiting for connection accepts
                    job.workflow_step = WorkflowStep.WAITING_FOR_ACCEPT
                    job.status = JobStatus.COMPLETED  # Completed this phase, but waiting

                else:
                    # All 1st degree skipped and no 2nd/3rd degree found either
                    # This means we have contacts but couldn't reach anyone new
                    logger.info(f"All {len(first_degree)} 1st degree connections were skipped (existing history)")
                    logger.info("No 2nd or 3rd degree people found to connect with")

                    await self._log_activity(
                        ActionType.ERROR,
                        f"All 1st degree contacts at {company} already messaged, no new people to contact",
                        {"company": company, "first_degree_skipped": len(first_degree)},
                        job_id=job.id,
                    )

                    job.workflow_step = WorkflowStep.DONE
                    job.status = JobStatus.FAILED
                    job.error_message = f"All {len(first_degree)} 1st degree contacts already messaged, no new contacts found"
                    job.processed_at = datetime.utcnow()

                    results["success"] = False
                    results["error"] = job.error_message

            elif second_degree:
                # No 1st degree found, but we have 2nd degree results
                # Connection requests were already sent directly from the search page
                results["steps_completed"].append("search_connections")
                logger.info(f"No 1st degree at {company}, sent connection requests to {len(second_degree)} 2nd degree")

                await self._log_activity(
                    ActionType.LINKEDIN_SEARCH,
                    f"Found and connected with 2nd degree people at {company}",
                    {"company": company, "results_count": len(second_degree)},
                    job_id=job.id,
                )

                # Don't save 2nd degree contacts - they'll become 1st degree when they accept
                # and we'll save them when we message them
                results["steps_completed"].append("search_linkedin")
                results["connection_requests_sent"] = len(second_degree)
                results["steps_completed"].append("send_requests")

                # Log connection requests sent (without saving contacts)
                for person in second_degree:
                    await self._log_activity(
                        ActionType.CONNECTION_REQUEST_SENT,
                        f"Connection request sent to {person.get('name', 'Unknown')}",
                        {"name": person.get("name"), "linkedin_url": person.get("linkedin_url")},
                        job_id=job.id,
                    )

                # Now waiting for connection accepts
                job.workflow_step = WorkflowStep.WAITING_FOR_ACCEPT
                job.status = JobStatus.COMPLETED  # Completed this phase, but waiting

            elif third_plus:
                # No 1st or 2nd degree found, but we have 3rd+ degree results
                # Connection requests were already sent directly from the search page
                results["steps_completed"].append("search_connections")
                logger.info(f"No 1st/2nd degree at {company}, sent connection requests to {len(third_plus)} 3rd+ degree")

                await self._log_activity(
                    ActionType.LINKEDIN_SEARCH,
                    f"Found and connected with 3rd+ degree people at {company}",
                    {"company": company, "results_count": len(third_plus)},
                    job_id=job.id,
                )

                # Don't save 3rd+ degree contacts - they'll become 1st degree when they accept
                # and we'll save them when we message them
                results["steps_completed"].append("search_linkedin")
                results["connection_requests_sent"] = len(third_plus)
                results["steps_completed"].append("send_requests")

                # Log connection requests sent (without saving contacts)
                for person in third_plus:
                    await self._log_activity(
                        ActionType.CONNECTION_REQUEST_SENT,
                        f"Connection request sent to {person.get('name', 'Unknown')}",
                        {"name": person.get("name"), "linkedin_url": person.get("linkedin_url")},
                        job_id=job.id,
                    )

                # Now waiting for connection accepts
                job.workflow_step = WorkflowStep.WAITING_FOR_ACCEPT
                job.status = JobStatus.COMPLETED  # Completed this phase, but waiting

            else:
                # No people found at all
                results["steps_completed"].append("search_connections")

                if first_degree_only:
                    # We were only checking for accepted connection requests (1st degree only)
                    # No new 1st degree found - stay in WAITING_FOR_ACCEPT state
                    logger.info(f"Check accepts: No new 1st degree connections found at {company} yet")

                    await self._log_activity(
                        ActionType.CONNECTION_SEARCH,
                        f"Checked for accepted connections at {company} - none yet",
                        {"company": company, "first_degree_only": True},
                        job_id=job.id,
                    )

                    # Stay in WAITING_FOR_ACCEPT - connection requests still pending
                    job.workflow_step = WorkflowStep.WAITING_FOR_ACCEPT
                    job.status = JobStatus.COMPLETED
                    job.last_reply_check_at = datetime.utcnow()  # Update check timestamp

                    results["success"] = True
                    results["steps_completed"].append("checked_accepts_none_yet")
                else:
                    # Normal search - no people found, mark as failed
                    error_msg = f"Could not find any people at '{company}' on LinkedIn"
                    logger.warning(error_msg)

                    await self._log_activity(
                        ActionType.ERROR,
                        error_msg,
                        {"company": company},
                        job_id=job.id,
                    )

                    job.workflow_step = WorkflowStep.DONE
                    job.status = JobStatus.FAILED
                    job.error_message = error_msg
                    job.processed_at = datetime.utcnow()

                    results["success"] = False
                    results["error"] = error_msg

        await self.db.flush()

        # Log warning if no steps were completed (should not happen normally)
        if not results["steps_completed"]:
            logger.warning(f"Job {job.id} completed workflow with no steps executed. Workflow step was: {job.workflow_step.value}")

        return results

    async def _get_template(self, template_id: int | None) -> Template | None:
        """Get template by ID or default template."""
        if template_id:
            result = await self.db.execute(
                select(Template).where(Template.id == template_id)
            )
            return result.scalar_one_or_none()

        # Get default template
        result = await self.db.execute(
            select(Template).where(Template.is_default == True)
        )
        template = result.scalar_one_or_none()

        if not template:
            # Get any template as fallback
            result = await self.db.execute(select(Template).limit(1))
            template = result.scalar_one_or_none()

        return template

    async def _save_contacts(
        self,
        job: Job,
        people: list[dict],
        is_connection: bool,
        already_messaged: bool = False
    ) -> list[Contact]:
        """Save found people as contacts in database.

        Args:
            job: The job these contacts are associated with
            people: List of people dicts from LinkedIn search
            is_connection: Whether these are existing connections (1st degree)
            already_messaged: Whether messages were already sent (from search page)
        """
        saved_contacts = []

        for person in people:
            linkedin_url = person.get("linkedin_url")
            if not linkedin_url:
                continue

            # Check if contact already exists
            result = await self.db.execute(
                select(Contact).where(Contact.linkedin_url == linkedin_url)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update job association if needed
                if not existing.job_id:
                    existing.job_id = job.id
                # Update message_sent_at if message was sent from search page
                if already_messaged and not existing.message_sent_at:
                    existing.message_sent_at = datetime.utcnow()
                saved_contacts.append(existing)
            else:
                name = person.get("name", "")

                # Create new contact
                contact = Contact(
                    linkedin_url=linkedin_url,
                    name=name,
                    company=job.company_name,
                    position=person.get("headline") or person.get("occupation"),
                    is_connection=is_connection,
                    job_id=job.id,
                    # Set message_sent_at if message was already sent from search page
                    message_sent_at=datetime.utcnow() if already_messaged else None,
                )
                self.db.add(contact)
                await self.db.flush()
                saved_contacts.append(contact)

        return saved_contacts

    async def _send_messages_to_contacts(
        self,
        job: Job,
        contacts: list[Contact],
        template: Template
    ) -> dict:
        """Send messages to existing connections."""
        result = {"sent": 0, "failed": 0}

        # Check if template contains Hebrew text
        template_has_hebrew = is_hebrew_text(template.content or "")

        for contact in contacts:
            if contact.message_sent_at:
                continue  # Already messaged

            try:
                # Get first name, translate to Hebrew if template is Hebrew
                first_name = contact.name.split()[0] if contact.name else ""
                if template_has_hebrew:
                    translated = await translate_name_to_hebrew(first_name, self.db)
                    if translated:
                        first_name = translated

                # Format message
                message = template.format_message(
                    name=first_name,
                    company=job.company_name,
                )

                # Send message using profile URL
                success = await self.client.send_message(
                    profile_url=contact.linkedin_url,
                    message=message,
                )

                if success:
                    contact.message_sent_at = datetime.utcnow()
                    contact.message_content = message
                    result["sent"] += 1

                    await self._log_activity(
                        ActionType.MESSAGE_SENT,
                        f"Message sent to {contact.name}",
                        {"contact_id": contact.id, "name": contact.name},
                        job_id=job.id,
                    )
                else:
                    result["failed"] += 1

            except Exception as e:
                logger.error(f"Error sending message to {contact.name}: {e}")
                result["failed"] += 1

        return result

    async def _send_connection_requests(
        self,
        job: Job,
        contacts: list[Contact],
        template: Template
    ) -> dict:
        """Send connection requests to non-connections."""
        result = {"sent": 0, "failed": 0}

        for contact in contacts:
            if contact.is_connection or contact.connection_requested_at:
                continue  # Already connected or requested

            try:
                # Generate personalized note (optional)
                note = f"Hi {contact.name.split()[0] if contact.name else 'there'}, " \
                       f"I noticed you work at {job.company_name}. " \
                       f"I'd love to connect!"

                # Truncate to LinkedIn's 300 char limit
                note = note[:300]

                # Send connection request using profile URL
                success = await self.client.send_connection_request(
                    profile_url=contact.linkedin_url,
                    note=note,
                )

                if success:
                    contact.connection_requested_at = datetime.utcnow()
                    result["sent"] += 1

                    await self._log_activity(
                        ActionType.CONNECTION_REQUEST_SENT,
                        f"Connection request sent to {contact.name}",
                        {"contact_id": contact.id, "name": contact.name},
                        job_id=job.id,
                    )
                else:
                    result["failed"] += 1

            except Exception as e:
                logger.error(f"Error sending connection request to {contact.name}: {e}")
                result["failed"] += 1

        return result

    async def _check_for_replies(self, job: Job) -> dict:
        """
        Check if any contacts we messaged have replied.

        Returns:
            Dict with reply_received=True if someone replied
        """
        # Get contacts we messaged for this job
        result = await self.db.execute(
            select(Contact).where(
                Contact.job_id == job.id,
                Contact.message_sent_at.isnot(None),
                Contact.reply_received_at.is_(None),  # Not already marked as replied
            )
        )
        contacts_to_check = result.scalars().all()

        if not contacts_to_check:
            logger.info(f"No contacts to check for replies for job {job.id}")
            return {"reply_received": False}

        # Convert to dicts for the LinkedIn client
        contacts_data = [
            {
                "name": c.name,
                "linkedin_url": c.linkedin_url,
                "public_id": c.linkedin_url.rstrip('/').split('/')[-1] if c.linkedin_url else "",
            }
            for c in contacts_to_check
        ]

        logger.info(f"Checking {len(contacts_data)} contacts for replies")

        # Check for replies using LinkedIn client
        result = await self.client.check_for_replies(contacts_data, job.company_name)

        replied = result.get("replied_contacts", [])
        failed = result.get("failed_contacts", [])

        if replied:
            # Mark the contacts that replied
            for replied_contact in replied:
                for contact in contacts_to_check:
                    if contact.name == replied_contact.get("name"):
                        contact.reply_received_at = datetime.utcnow()
                        logger.info(f"Marked reply received from {contact.name}")

                        await self._log_activity(
                            ActionType.MESSAGE_SENT,  # Or create a new action type for replies
                            f"Received reply from {contact.name}!",
                            {"contact_id": contact.id, "name": contact.name},
                            job_id=job.id,
                        )
                        break

            return {"reply_received": True, "replied_contacts": replied}

        # If some contacts failed to check, report that to the user
        if failed:
            failed_names = [f.get("name", "Unknown") for f in failed]
            logger.warning(f"Failed to check replies from: {failed_names}")
            return {
                "reply_received": False,
                "check_failed": True,
                "failed_contacts": failed,
                "error": f"Could not check replies from: {', '.join(failed_names)}. LinkedIn was unresponsive. Please try again."
            }

        return {"reply_received": False}

    async def _log_activity(
        self,
        action_type: ActionType,
        description: str,
        details: dict,
        job_id: int | None = None,
    ):
        """Log an activity."""
        activity = ActivityLog(
            action_type=action_type,
            description=description,
            details=details,
            job_id=job_id,
        )
        self.db.add(activity)

    async def close(self):
        """Clean up resources."""
        self.client = None


async def run_workflow_background(job_id: int, db: AsyncSession, template_id: int | None = None):
    """Background task wrapper for workflow execution."""
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.run_workflow(job_id, template_id)
        await db.commit()
        return result
    except Exception as e:
        await db.rollback()
        raise
