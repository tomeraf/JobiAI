"""
Integration tests for workflow orchestration.

Tests the ACTUAL WorkflowOrchestrator logic:
1. Workflow state transitions
2. Hebrew name translation pause/resume
3. Multi-degree fallback (1st → 2nd → 3rd)
4. Reply checking
5. Contact saving
6. Activity logging
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.job import Job, JobStatus, WorkflowStep
from app.models.contact import Contact
from app.models.template import Template
from app.models.activity import ActivityLog, ActionType
from app.services.workflow_orchestrator import WorkflowOrchestrator
from app.services.linkedin.client import MissingHebrewNamesException, WorkflowAbortedException
from app.services.hebrew_names import translate_name_to_hebrew, is_hebrew_text


class TestHebrewNameTranslation:
    """Test Hebrew name translation service (real logic)."""

    @pytest.mark.asyncio
    async def test_translate_known_name(self, db_session: AsyncSession):
        """Should translate known names from dictionary."""
        result = await translate_name_to_hebrew("David", db_session)
        assert result == "דוד"

    @pytest.mark.asyncio
    async def test_translate_name_case_insensitive(self, db_session: AsyncSession):
        """Translation should be case-insensitive."""
        result1 = await translate_name_to_hebrew("DAVID", db_session)
        result2 = await translate_name_to_hebrew("david", db_session)
        result3 = await translate_name_to_hebrew("David", db_session)
        assert result1 == result2 == result3 == "דוד"

    @pytest.mark.asyncio
    async def test_translate_unknown_name_returns_none(self, db_session: AsyncSession):
        """Unknown names should return None."""
        result = await translate_name_to_hebrew("XyzUnknownName", db_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_translate_already_hebrew_name(self, db_session: AsyncSession):
        """Hebrew names should be returned as-is."""
        result = await translate_name_to_hebrew("דוד", db_session)
        assert result == "דוד"

    @pytest.mark.asyncio
    async def test_translate_from_database(self, db_session: AsyncSession, hebrew_names):
        """Should find names from database."""
        # hebrew_names fixture creates david, sarah, michael
        result = await translate_name_to_hebrew("david", db_session)
        assert result is not None

    def test_is_hebrew_text_detection(self):
        """Should correctly detect Hebrew text."""
        assert is_hebrew_text("היי {name}") is True
        assert is_hebrew_text("Hello {name}") is False
        assert is_hebrew_text("") is False
        assert is_hebrew_text("Mixed שלום text") is True


class TestWorkflowOrchestratorBasicFlow:
    """Test basic workflow orchestrator flow."""

    @pytest.mark.asyncio
    async def test_workflow_requires_company_name(self, db_session: AsyncSession):
        """Workflow should fail if company_name is not set."""
        job = Job(url="https://example.com/jobs/123", status=JobStatus.PENDING)
        db_session.add(job)
        await db_session.flush()

        orchestrator = WorkflowOrchestrator(db_session)
        result = await orchestrator.run_workflow(job.id)

        assert result["success"] is False
        assert "company" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_workflow_requires_template(self, db_session: AsyncSession):
        """Workflow should fail if no template exists."""
        job = Job(
            url="https://example.com/jobs/123",
            company_name="TestCorp",
            status=JobStatus.COMPLETED
        )
        db_session.add(job)
        await db_session.flush()

        orchestrator = WorkflowOrchestrator(db_session)
        result = await orchestrator.run_workflow(job.id)

        assert result["success"] is False
        assert "template" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_workflow_nonexistent_job(self, db_session: AsyncSession):
        """Workflow should handle nonexistent job."""
        orchestrator = WorkflowOrchestrator(db_session)
        result = await orchestrator.run_workflow(99999)

        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestWorkflowWithMockedLinkedIn:
    """Test workflow with mocked LinkedIn services."""

    @pytest.fixture
    def mock_linkedin_services(self):
        """Mock all LinkedIn services."""
        with patch("app.services.workflow_orchestrator.LinkedInSearch") as MockSearch, \
             patch("app.services.workflow_orchestrator.LinkedInMessaging") as MockMessaging, \
             patch("app.services.workflow_orchestrator.LinkedInConnections") as MockConnections, \
             patch("app.services.workflow_orchestrator.LinkedInClient") as MockClient:

            # Setup search mock
            mock_search = MagicMock()
            MockSearch.return_value = mock_search

            # Setup messaging mock
            mock_messaging = MagicMock()
            MockMessaging.return_value = mock_messaging

            # Setup connections mock
            mock_connections = MagicMock()
            MockConnections.return_value = mock_connections

            # Setup client mock (singleton)
            mock_client = MagicMock()
            mock_client.check_abort = MagicMock()  # No-op
            mock_client.clear_abort = MagicMock()
            mock_client.set_current_job = MagicMock()
            mock_client.check_for_replies = AsyncMock(return_value=[])
            MockClient.get_instance = MagicMock(return_value=mock_client)

            yield {
                "search": mock_search,
                "messaging": mock_messaging,
                "connections": mock_connections,
                "client": mock_client
            }

    @pytest.mark.asyncio
    async def test_workflow_with_first_degree_connections(
        self, db_session: AsyncSession, job_with_company: Job,
        english_template: Template, mock_linkedin_services
    ):
        """Workflow should message 1st degree connections."""
        # Setup: make template default
        english_template.is_default = True
        await db_session.flush()

        # Mock search results with 1st degree and messages sent
        mock_linkedin_services["search"].search_company_all_degrees = AsyncMock(return_value={
            "first_degree": [
                {"name": "John Doe", "linkedin_url": "https://linkedin.com/in/john", "company": "Acme"}
            ],
            "second_degree": [],
            "third_plus": [],
            "messages_sent": [
                {"name": "John Doe", "linkedin_url": "https://linkedin.com/in/john"}
            ]
        })

        orchestrator = WorkflowOrchestrator(db_session)
        result = await orchestrator.run_workflow(job_with_company.id)

        assert result["success"] is True
        assert result["messages_sent"] == 1
        assert "message_connections" in result["steps_completed"]

        await db_session.refresh(job_with_company)
        assert job_with_company.workflow_step == WorkflowStep.WAITING_FOR_REPLY

    @pytest.mark.asyncio
    async def test_workflow_fallback_to_second_degree(
        self, db_session: AsyncSession, job_with_company: Job,
        english_template: Template, mock_linkedin_services
    ):
        """Should fall back to 2nd degree when no 1st degree found."""
        english_template.is_default = True
        await db_session.flush()

        # No 1st degree, but 2nd degree found
        mock_linkedin_services["search"].search_company_all_degrees = AsyncMock(return_value={
            "first_degree": [],
            "second_degree": [
                {"name": "Bob Wilson", "linkedin_url": "https://linkedin.com/in/bob", "company": "Acme"}
            ],
            "third_plus": [],
            "messages_sent": []
        })

        orchestrator = WorkflowOrchestrator(db_session)
        result = await orchestrator.run_workflow(job_with_company.id)

        assert result["success"] is True
        assert result["connection_requests_sent"] == 1
        assert "send_requests" in result["steps_completed"]

        await db_session.refresh(job_with_company)
        assert job_with_company.workflow_step == WorkflowStep.WAITING_FOR_ACCEPT

    @pytest.mark.asyncio
    async def test_workflow_fallback_to_third_degree(
        self, db_session: AsyncSession, job_with_company: Job,
        english_template: Template, mock_linkedin_services
    ):
        """Should fall back to 3rd+ degree when no 1st or 2nd found."""
        english_template.is_default = True
        await db_session.flush()

        # No 1st or 2nd degree, only 3rd+
        mock_linkedin_services["search"].search_company_all_degrees = AsyncMock(return_value={
            "first_degree": [],
            "second_degree": [],
            "third_plus": [
                {"name": "Alice Brown", "linkedin_url": "https://linkedin.com/in/alice", "company": "Acme"}
            ],
            "messages_sent": []
        })

        orchestrator = WorkflowOrchestrator(db_session)
        result = await orchestrator.run_workflow(job_with_company.id)

        assert result["success"] is True
        assert result["connection_requests_sent"] == 1

        await db_session.refresh(job_with_company)
        assert job_with_company.workflow_step == WorkflowStep.WAITING_FOR_ACCEPT

    @pytest.mark.asyncio
    async def test_workflow_no_connections_found_fails(
        self, db_session: AsyncSession, job_with_company: Job,
        english_template: Template, mock_linkedin_services
    ):
        """Should fail when no connections found at all."""
        english_template.is_default = True
        await db_session.flush()

        # No one found
        mock_linkedin_services["search"].search_company_all_degrees = AsyncMock(return_value={
            "first_degree": [],
            "second_degree": [],
            "third_plus": [],
            "messages_sent": []
        })

        orchestrator = WorkflowOrchestrator(db_session)
        result = await orchestrator.run_workflow(job_with_company.id)

        assert result["success"] is False
        assert "could not find" in result["error"].lower()

        await db_session.refresh(job_with_company)
        assert job_with_company.status == JobStatus.FAILED


class TestHebrewNameWorkflowPause:
    """Test workflow pausing for Hebrew name translations."""

    @pytest.fixture
    def mock_linkedin_for_hebrew(self):
        """Mock LinkedIn to trigger Hebrew name exception."""
        with patch("app.services.workflow_orchestrator.LinkedInSearch") as MockSearch, \
             patch("app.services.workflow_orchestrator.LinkedInMessaging") as MockMessaging, \
             patch("app.services.workflow_orchestrator.LinkedInConnections") as MockConnections, \
             patch("app.services.workflow_orchestrator.LinkedInClient") as MockClient:

            mock_search = MagicMock()
            MockSearch.return_value = mock_search

            mock_client = MagicMock()
            mock_client.check_abort = MagicMock()
            mock_client.clear_abort = MagicMock()
            mock_client.set_current_job = MagicMock()
            MockClient.get_instance = MagicMock(return_value=mock_client)

            yield {"search": mock_search, "client": mock_client}

    @pytest.mark.asyncio
    async def test_workflow_pauses_for_missing_hebrew_name(
        self, db_session: AsyncSession, job_with_company: Job,
        default_template: Template, mock_linkedin_for_hebrew
    ):
        """Workflow should pause when Hebrew translation is missing."""
        # default_template is Hebrew, so translations are needed

        # Mock search to raise MissingHebrewNamesException
        mock_linkedin_for_hebrew["search"].search_company_all_degrees = AsyncMock(
            side_effect=MissingHebrewNamesException(
                missing_names=["UnknownPerson"],
                first_degree_found=[]
            )
        )

        orchestrator = WorkflowOrchestrator(db_session)
        result = await orchestrator.run_workflow(job_with_company.id)

        # Should succeed but pause
        assert result["success"] is True
        assert result.get("needs_hebrew_names") == ["UnknownPerson"]

        await db_session.refresh(job_with_company)
        assert job_with_company.workflow_step == WorkflowStep.NEEDS_HEBREW_NAMES
        assert job_with_company.status == JobStatus.NEEDS_INPUT
        assert "UnknownPerson" in job_with_company.pending_hebrew_names

    @pytest.mark.asyncio
    async def test_workflow_resumes_after_hebrew_names_provided(
        self, db_session: AsyncSession, default_template: Template, mock_linkedin_for_hebrew
    ):
        """Workflow should resume after user provides Hebrew translations."""
        # Create job in NEEDS_HEBREW_NAMES state
        job = Job(
            url="https://example.com/jobs/123",
            company_name="Acme Corp",
            status=JobStatus.NEEDS_INPUT,
            workflow_step=WorkflowStep.NEEDS_HEBREW_NAMES,
            pending_hebrew_names=["John"]
        )
        db_session.add(job)
        await db_session.flush()

        # Mock successful search after Hebrew names provided
        mock_linkedin_for_hebrew["search"].search_company_all_degrees = AsyncMock(return_value={
            "first_degree": [
                {"name": "John Doe", "linkedin_url": "https://linkedin.com/in/john"}
            ],
            "second_degree": [],
            "third_plus": [],
            "messages_sent": [
                {"name": "John Doe", "linkedin_url": "https://linkedin.com/in/john"}
            ]
        })

        orchestrator = WorkflowOrchestrator(db_session)
        result = await orchestrator.run_workflow(job.id)

        assert result["success"] is True
        assert result["messages_sent"] == 1

        await db_session.refresh(job)
        # After resuming, workflow should be in WAITING_FOR_REPLY or MESSAGE_CONNECTIONS
        # depending on implementation - both are valid completed states
        assert job.workflow_step in [WorkflowStep.WAITING_FOR_REPLY, WorkflowStep.MESSAGE_CONNECTIONS]
        assert job.pending_hebrew_names is None


class TestWorkflowAbort:
    """Test workflow abort functionality."""

    @pytest.mark.asyncio
    async def test_abort_returns_aborted_result(self, db_session: AsyncSession, english_template: Template):
        """Aborting should return aborted=True in result."""
        # Create a fresh job for this test
        job = Job(
            url="https://example.com/jobs/123",
            company_name="TestCorp",
            status=JobStatus.PENDING,
            workflow_step=WorkflowStep.COMPANY_EXTRACTION
        )
        db_session.add(job)
        english_template.is_default = True
        await db_session.flush()

        with patch("app.services.workflow_orchestrator.LinkedInSearch") as MockSearch, \
             patch("app.services.workflow_orchestrator.LinkedInMessaging") as MockMessaging, \
             patch("app.services.workflow_orchestrator.LinkedInConnections") as MockConnections, \
             patch("app.services.workflow_orchestrator.LinkedInClient") as MockClient:

            mock_client = MagicMock()
            mock_client.clear_abort = MagicMock()
            mock_client.set_current_job = MagicMock()
            # Simulate abort being triggered during workflow
            mock_client.check_abort = MagicMock(side_effect=WorkflowAbortedException())
            MockClient.get_instance = MagicMock(return_value=mock_client)

            orchestrator = WorkflowOrchestrator(db_session)
            result = await orchestrator.run_workflow(job.id)

            # Test that abort is properly handled and returns correct result
            assert result["success"] is False
            assert result.get("aborted") is True


class TestReplyChecking:
    """Test reply checking workflow."""

    @pytest.mark.asyncio
    async def test_reply_detected_returns_reply_step(
        self, db_session: AsyncSession, job_waiting_for_reply: Job,
        default_template: Template, messaged_contacts
    ):
        """Workflow should return reply_received step when reply detected."""
        with patch("app.services.workflow_orchestrator.LinkedInSearch") as MockSearch, \
             patch("app.services.workflow_orchestrator.LinkedInMessaging") as MockMessaging, \
             patch("app.services.workflow_orchestrator.LinkedInConnections") as MockConnections, \
             patch("app.services.workflow_orchestrator.LinkedInClient") as MockClient:

            mock_client = MagicMock()
            mock_client.check_abort = MagicMock()
            mock_client.clear_abort = MagicMock()
            mock_client.set_current_job = MagicMock()
            # Mock reply detection - return the contact that replied
            mock_client.check_for_replies = AsyncMock(return_value=[
                {"name": "John Doe"}
            ])
            MockClient.get_instance = MagicMock(return_value=mock_client)

            orchestrator = WorkflowOrchestrator(db_session)
            result = await orchestrator.run_workflow(job_waiting_for_reply.id, force_search=False)

            # Test that reply detection returns correct result
            assert result["success"] is True
            assert "reply_received" in result["steps_completed"]

    @pytest.mark.asyncio
    async def test_no_reply_stays_in_waiting(
        self, db_session: AsyncSession, job_waiting_for_reply: Job,
        default_template: Template, messaged_contacts
    ):
        """Should stay in WAITING_FOR_REPLY if no reply."""
        with patch("app.services.workflow_orchestrator.LinkedInSearch") as MockSearch, \
             patch("app.services.workflow_orchestrator.LinkedInMessaging") as MockMessaging, \
             patch("app.services.workflow_orchestrator.LinkedInConnections") as MockConnections, \
             patch("app.services.workflow_orchestrator.LinkedInClient") as MockClient:

            mock_client = MagicMock()
            mock_client.check_abort = MagicMock()
            mock_client.clear_abort = MagicMock()
            mock_client.set_current_job = MagicMock()
            mock_client.check_for_replies = AsyncMock(return_value=[])
            MockClient.get_instance = MagicMock(return_value=mock_client)

            orchestrator = WorkflowOrchestrator(db_session)
            result = await orchestrator.run_workflow(job_waiting_for_reply.id, force_search=False)

            assert result["success"] is True
            assert "checked_replies_none_yet" in result["steps_completed"]

            await db_session.refresh(job_waiting_for_reply)
            assert job_waiting_for_reply.workflow_step == WorkflowStep.WAITING_FOR_REPLY

    @pytest.mark.asyncio
    async def test_force_search_searches_for_new_people(
        self, db_session: AsyncSession, job_waiting_for_reply: Job,
        english_template: Template
    ):
        """force_search=True should search for new people to message."""
        english_template.is_default = True
        await db_session.flush()

        with patch("app.services.workflow_orchestrator.LinkedInSearch") as MockSearch, \
             patch("app.services.workflow_orchestrator.LinkedInMessaging") as MockMessaging, \
             patch("app.services.workflow_orchestrator.LinkedInConnections") as MockConnections, \
             patch("app.services.workflow_orchestrator.LinkedInClient") as MockClient:

            mock_client = MagicMock()
            mock_client.check_abort = MagicMock()
            mock_client.clear_abort = MagicMock()
            mock_client.set_current_job = MagicMock()
            MockClient.get_instance = MagicMock(return_value=mock_client)

            mock_search = MagicMock()
            mock_search.search_company_all_degrees = AsyncMock(return_value={
                "first_degree": [
                    {"name": "New Person", "linkedin_url": "https://linkedin.com/in/new"}
                ],
                "second_degree": [],
                "third_plus": [],
                "messages_sent": [
                    {"name": "New Person", "linkedin_url": "https://linkedin.com/in/new"}
                ]
            })
            MockSearch.return_value = mock_search

            orchestrator = WorkflowOrchestrator(db_session)
            result = await orchestrator.run_workflow(job_waiting_for_reply.id, force_search=True)

            # Should search for new people
            assert result["success"] is True
            mock_search.search_company_all_degrees.assert_called_once()


class TestContactSaving:
    """Test that contacts are saved correctly."""

    @pytest.fixture
    def mock_linkedin_contacts(self):
        """Mock LinkedIn services for contact tests."""
        with patch("app.services.workflow_orchestrator.LinkedInSearch") as MockSearch, \
             patch("app.services.workflow_orchestrator.LinkedInMessaging") as MockMessaging, \
             patch("app.services.workflow_orchestrator.LinkedInConnections") as MockConnections, \
             patch("app.services.workflow_orchestrator.LinkedInClient") as MockClient:

            mock_search = MagicMock()
            MockSearch.return_value = mock_search

            mock_client = MagicMock()
            mock_client.check_abort = MagicMock()
            mock_client.clear_abort = MagicMock()
            mock_client.set_current_job = MagicMock()
            MockClient.get_instance = MagicMock(return_value=mock_client)

            yield mock_search

    @pytest.mark.asyncio
    async def test_messaged_contacts_saved(
        self, db_session: AsyncSession, job_with_company: Job,
        english_template: Template, mock_linkedin_contacts
    ):
        """Contacts that receive messages should be saved."""
        english_template.is_default = True
        await db_session.flush()

        mock_linkedin_contacts.search_company_all_degrees = AsyncMock(return_value={
            "first_degree": [
                {"name": "John Doe", "linkedin_url": "https://linkedin.com/in/john-test", "headline": "Engineer"}
            ],
            "second_degree": [],
            "third_plus": [],
            "messages_sent": [
                {"name": "John Doe", "linkedin_url": "https://linkedin.com/in/john-test"}
            ]
        })

        orchestrator = WorkflowOrchestrator(db_session)
        await orchestrator.run_workflow(job_with_company.id)

        # Check contact was saved
        result = await db_session.execute(
            select(Contact).where(Contact.linkedin_url == "https://linkedin.com/in/john-test")
        )
        contact = result.scalar_one_or_none()

        assert contact is not None
        assert contact.name == "John Doe"
        assert contact.job_id == job_with_company.id
        assert contact.is_connection is True
        assert contact.message_sent_at is not None

    @pytest.mark.asyncio
    async def test_duplicate_contacts_not_created(
        self, db_session: AsyncSession, job_with_company: Job,
        english_template: Template, mock_linkedin_contacts
    ):
        """Should not create duplicate contacts."""
        english_template.is_default = True

        # Create existing contact
        existing = Contact(
            linkedin_url="https://linkedin.com/in/existing",
            name="Existing Contact",
            company="Acme Corp",
            is_connection=True,
            job_id=job_with_company.id
        )
        db_session.add(existing)
        await db_session.flush()

        mock_linkedin_contacts.search_company_all_degrees = AsyncMock(return_value={
            "first_degree": [
                {"name": "Existing Contact", "linkedin_url": "https://linkedin.com/in/existing"}
            ],
            "second_degree": [],
            "third_plus": [],
            "messages_sent": [
                {"name": "Existing Contact", "linkedin_url": "https://linkedin.com/in/existing"}
            ]
        })

        orchestrator = WorkflowOrchestrator(db_session)
        await orchestrator.run_workflow(job_with_company.id)

        # Should only have one contact with that URL
        result = await db_session.execute(
            select(Contact).where(Contact.linkedin_url == "https://linkedin.com/in/existing")
        )
        contacts = result.scalars().all()
        assert len(contacts) == 1


class TestActivityLogging:
    """Test that activities are logged correctly."""

    @pytest.fixture
    def mock_linkedin_logging(self):
        """Mock LinkedIn for logging tests."""
        with patch("app.services.workflow_orchestrator.LinkedInSearch") as MockSearch, \
             patch("app.services.workflow_orchestrator.LinkedInMessaging") as MockMessaging, \
             patch("app.services.workflow_orchestrator.LinkedInConnections") as MockConnections, \
             patch("app.services.workflow_orchestrator.LinkedInClient") as MockClient:

            mock_search = MagicMock()
            MockSearch.return_value = mock_search

            mock_client = MagicMock()
            mock_client.check_abort = MagicMock()
            mock_client.clear_abort = MagicMock()
            mock_client.set_current_job = MagicMock()
            MockClient.get_instance = MagicMock(return_value=mock_client)

            yield mock_search

    @pytest.mark.asyncio
    async def test_connection_search_logged(
        self, db_session: AsyncSession, job_with_company: Job,
        english_template: Template, mock_linkedin_logging
    ):
        """CONNECTION_SEARCH activity should be logged."""
        english_template.is_default = True
        await db_session.flush()

        mock_linkedin_logging.search_company_all_degrees = AsyncMock(return_value={
            "first_degree": [],
            "second_degree": [],
            "third_plus": [],
            "messages_sent": []
        })

        orchestrator = WorkflowOrchestrator(db_session)
        await orchestrator.run_workflow(job_with_company.id)

        result = await db_session.execute(
            select(ActivityLog).where(
                ActivityLog.job_id == job_with_company.id,
                ActivityLog.action_type == ActionType.CONNECTION_SEARCH
            )
        )
        log = result.scalar_one_or_none()
        assert log is not None
        assert job_with_company.company_name in log.description

    @pytest.mark.asyncio
    async def test_message_sent_logged(
        self, db_session: AsyncSession, job_with_company: Job,
        english_template: Template, mock_linkedin_logging
    ):
        """MESSAGE_SENT activities should be logged."""
        english_template.is_default = True
        await db_session.flush()

        mock_linkedin_logging.search_company_all_degrees = AsyncMock(return_value={
            "first_degree": [
                {"name": "John Doe", "linkedin_url": "https://linkedin.com/in/john"}
            ],
            "second_degree": [],
            "third_plus": [],
            "messages_sent": [
                {"name": "John Doe", "linkedin_url": "https://linkedin.com/in/john"}
            ]
        })

        orchestrator = WorkflowOrchestrator(db_session)
        await orchestrator.run_workflow(job_with_company.id)

        result = await db_session.execute(
            select(ActivityLog).where(
                ActivityLog.job_id == job_with_company.id,
                ActivityLog.action_type == ActionType.MESSAGE_SENT
            )
        )
        logs = result.scalars().all()
        assert len(logs) >= 1
        assert any("John Doe" in log.description for log in logs)

    @pytest.mark.asyncio
    async def test_connection_request_logged(
        self, db_session: AsyncSession, job_with_company: Job,
        english_template: Template, mock_linkedin_logging
    ):
        """CONNECTION_REQUEST_SENT activities should be logged."""
        english_template.is_default = True
        await db_session.flush()

        mock_linkedin_logging.search_company_all_degrees = AsyncMock(return_value={
            "first_degree": [],
            "second_degree": [
                {"name": "Bob Wilson", "linkedin_url": "https://linkedin.com/in/bob"}
            ],
            "third_plus": [],
            "messages_sent": []
        })

        orchestrator = WorkflowOrchestrator(db_session)
        await orchestrator.run_workflow(job_with_company.id)

        result = await db_session.execute(
            select(ActivityLog).where(
                ActivityLog.job_id == job_with_company.id,
                ActivityLog.action_type == ActionType.CONNECTION_REQUEST_SENT
            )
        )
        logs = result.scalars().all()
        assert len(logs) >= 1
        assert any("Bob Wilson" in log.description for log in logs)
