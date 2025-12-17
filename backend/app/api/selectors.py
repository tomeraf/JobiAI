from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.site_selector import SiteSelector
from app.models.activity import ActivityLog, ActionType
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class SelectorCreate(BaseModel):
    domain: str
    company_selector: str
    title_selector: str | None = None
    example_url: str | None = None
    example_company: str | None = None


class SelectorUpdate(BaseModel):
    company_selector: str | None = None
    title_selector: str | None = None


class SelectorResponse(BaseModel):
    id: int
    domain: str
    company_selector: str | None = None
    title_selector: str | None = None
    example_url: str | None = None
    example_company: str | None = None
    site_type: str | None = None
    company_name: str | None = None
    platform_name: str | None = None
    url_pattern: str | None = None
    created_at: datetime
    last_used_at: datetime | None = None

    class Config:
        from_attributes = True


@router.post("", response_model=SelectorResponse)
async def create_selector(
    selector_data: SelectorCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new site selector (learn a new job site)."""
    # Check if domain already exists
    result = await db.execute(
        select(SiteSelector).where(SiteSelector.domain == selector_data.domain)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Selector for domain {selector_data.domain} already exists"
        )

    selector = SiteSelector(**selector_data.model_dump())
    db.add(selector)
    await db.flush()
    await db.refresh(selector)

    # Log the learning
    activity = ActivityLog(
        action_type=ActionType.SELECTOR_LEARNED,
        description=f"Learned selector for domain: {selector_data.domain}",
        details={
            "domain": selector_data.domain,
            "company_selector": selector_data.company_selector,
        },
    )
    db.add(activity)

    logger.info(f"Created selector for domain: {selector_data.domain}")
    return selector


@router.get("", response_model=list[SelectorResponse])
async def list_selectors(db: AsyncSession = Depends(get_db)):
    """List all learned site selectors."""
    result = await db.execute(
        select(SiteSelector).order_by(SiteSelector.last_used_at.desc().nulls_last())
    )
    return result.scalars().all()


@router.get("/domain/{domain}", response_model=SelectorResponse)
async def get_selector_by_domain(domain: str, db: AsyncSession = Depends(get_db)):
    """Get selector for a specific domain."""
    result = await db.execute(
        select(SiteSelector).where(SiteSelector.domain == domain)
    )
    selector = result.scalar_one_or_none()

    if not selector:
        raise HTTPException(status_code=404, detail=f"No selector for domain: {domain}")

    return selector


@router.get("/{selector_id}", response_model=SelectorResponse)
async def get_selector(selector_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific selector by ID."""
    result = await db.execute(
        select(SiteSelector).where(SiteSelector.id == selector_id)
    )
    selector = result.scalar_one_or_none()

    if not selector:
        raise HTTPException(status_code=404, detail="Selector not found")

    return selector


@router.put("/{selector_id}", response_model=SelectorResponse)
async def update_selector(
    selector_id: int,
    selector_data: SelectorUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a selector."""
    result = await db.execute(
        select(SiteSelector).where(SiteSelector.id == selector_id)
    )
    selector = result.scalar_one_or_none()

    if not selector:
        raise HTTPException(status_code=404, detail="Selector not found")

    update_data = selector_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(selector, field, value)

    await db.flush()
    await db.refresh(selector)

    logger.info(f"Updated selector for domain: {selector.domain}")
    return selector


@router.delete("/{selector_id}")
async def delete_selector(selector_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a selector."""
    result = await db.execute(
        select(SiteSelector).where(SiteSelector.id == selector_id)
    )
    selector = result.scalar_one_or_none()

    if not selector:
        raise HTTPException(status_code=404, detail="Selector not found")

    domain = selector.domain
    await db.delete(selector)
    logger.info(f"Deleted selector for domain: {domain}")
    return {"message": f"Selector for {domain} deleted"}


@router.post("/check")
async def check_domain(
    url: str,
    db: AsyncSession = Depends(get_db),
):
    """Check if we have a selector for the given URL's domain."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix if present
        if domain.startswith("www."):
            domain = domain[4:]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL")

    result = await db.execute(
        select(SiteSelector).where(SiteSelector.domain == domain)
    )
    selector = result.scalar_one_or_none()

    return {
        "domain": domain,
        "has_selector": selector is not None,
        "selector": SelectorResponse.model_validate(selector) if selector else None,
    }
