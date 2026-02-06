import enum
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SiteType(str, enum.Enum):
    """Type of job site."""
    COMPANY = "company"  # Company's own career page
    PLATFORM = "platform"  # Job platform hosting multiple companies (like greenhouse)


class SiteSelector(Base):
    """
    Stores learned URL patterns for job sites.

    For company websites: domain maps directly to company name
    For platforms: domain + URL pattern extracts company name from URL
    """
    __tablename__ = "site_selectors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Type of site (company website or job platform)
    site_type: Mapped[SiteType] = mapped_column(
        Enum(SiteType, values_callable=lambda x: [e.value for e in x]),
        default=SiteType.COMPANY,
        nullable=False
    )

    # For COMPANY type: the company name
    # For PLATFORM type: the platform name (e.g., "Greenhouse", "Lever")
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # URL pattern for extracting company from platform URLs (regex)
    # e.g., r"boards\.greenhouse\.io/([^/]+)" extracts company from path
    url_pattern: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Legacy CSS selectors (kept for backward compatibility, but not actively used)
    company_selector: Mapped[str | None] = mapped_column(Text, nullable=True)
    title_selector: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Example URL and extracted values for reference
    example_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_company: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<SiteSelector(id={self.id}, domain={self.domain}, type={self.site_type})>"
