from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class ActionType(str, enum.Enum):
    JOB_SUBMITTED = "job_submitted"
    COMPANY_EXTRACTED = "company_extracted"
    COMPANY_INPUT_NEEDED = "company_input_needed"  # Unknown site, need user input
    SELECTOR_LEARNED = "selector_learned"
    CONNECTION_SEARCH = "connection_search"
    CONNECTION_FOUND = "connection_found"
    CONNECTION_REQUEST_SENT = "connection_request_sent"
    MESSAGE_SENT = "message_sent"
    LINKEDIN_SEARCH = "linkedin_search"
    ERROR = "error"


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    action_type: Mapped[ActionType] = mapped_column(
        Enum(ActionType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Foreign key to related job (optional)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="activity_logs")

    def __repr__(self) -> str:
        return f"<ActivityLog(id={self.id}, action={self.action_type}, desc={self.description[:50]})>"
