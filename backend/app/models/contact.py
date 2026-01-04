from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    linkedin_url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_connection: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    connection_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    message_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    message_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_received_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )  # When they replied to our message

    # Foreign key to job that triggered this contact
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="contacts")

    def __repr__(self) -> str:
        return f"<Contact(id={self.id}, name={self.name}, company={self.company})>"
