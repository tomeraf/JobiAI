from datetime import datetime
from sqlalchemy import String, Text, DateTime, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    NEEDS_INPUT = "needs_input"  # Waiting for user to provide company name
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowStep(str, enum.Enum):
    """Tracks the current step in the job workflow."""
    COMPANY_EXTRACTION = "company_extraction"  # Step 1: Extract company from URL
    SEARCH_CONNECTIONS = "search_connections"  # Step 2: Search existing connections
    NEEDS_HEBREW_NAMES = "needs_hebrew_names"  # Step 2.5: Waiting for Hebrew name translations
    MESSAGE_CONNECTIONS = "message_connections"  # Step 3: Message found connections
    SEARCH_LINKEDIN = "search_linkedin"  # Step 4: Search LinkedIn for people
    SEND_REQUESTS = "send_requests"  # Step 5: Send connection requests
    DONE = "done"  # Workflow complete


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, values_callable=lambda x: [e.value for e in x]),
        default=JobStatus.PENDING,
        nullable=False
    )
    workflow_step: Mapped[WorkflowStep] = mapped_column(
        Enum(WorkflowStep, values_callable=lambda x: [e.value for e in x]),
        default=WorkflowStep.COMPANY_EXTRACTION,
        nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pending_hebrew_names: Mapped[list | None] = mapped_column(JSON, nullable=True)  # Names awaiting Hebrew translation
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    contacts: Mapped[list["Contact"]] = relationship(
        "Contact", back_populates="job", lazy="selectin"
    )
    activity_logs: Mapped[list["ActivityLog"]] = relationship(
        "ActivityLog", back_populates="job", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, company={self.company_name}, status={self.status})>"
