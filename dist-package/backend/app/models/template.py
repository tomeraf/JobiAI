from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Message content with placeholders: {name}/{שם}, {company}/{חברה}
    content: Mapped[str] = mapped_column(Text, nullable=False)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def format_message(self, name: str, company: str) -> str:
        """Format the message with the given variables.

        Supports both Hebrew and English placeholders:
        - Hebrew: {שם}, {חברה}
        - English: {name}, {company}
        """
        result = self.content
        # Replace Hebrew placeholders
        result = result.replace("{שם}", name).replace("{חברה}", company)
        # Replace English placeholders
        result = result.replace("{name}", name).replace("{company}", company)
        return result

    def __repr__(self) -> str:
        return f"<Template(id={self.id}, name={self.name}, default={self.is_default})>"
