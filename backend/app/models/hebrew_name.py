"""Model for storing user-provided Hebrew name translations."""
from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HebrewName(Base):
    """Stores mappings from English names to Hebrew script."""
    __tablename__ = "hebrew_names"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    english_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hebrew_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<HebrewName({self.english_name} -> {self.hebrew_name})>"
