from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.template import Template
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class TemplateCreate(BaseModel):
    name: str
    content: str
    is_default: bool = False


class TemplateUpdate(BaseModel):
    name: str | None = None
    content: str | None = None
    is_default: bool | None = None


class TemplateResponse(BaseModel):
    id: int
    name: str
    content: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplatePreview(BaseModel):
    name: str = "ישראל"
    company: str = "Google"


@router.post("", response_model=TemplateResponse)
async def create_template(
    template_data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new message template."""
    # If setting as default, unset other defaults
    if template_data.is_default:
        await db.execute(
            update(Template).values(is_default=False)
        )

    template = Template(**template_data.model_dump())
    db.add(template)
    await db.flush()
    await db.refresh(template)

    logger.info(f"Created template: {template.name}")
    return template


@router.get("", response_model=list[TemplateResponse])
async def list_templates(db: AsyncSession = Depends(get_db)):
    """List all message templates."""
    result = await db.execute(
        select(Template).order_by(Template.is_default.desc(), Template.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific template by ID."""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    template_data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a template."""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # If setting as default, unset other defaults
    if template_data.is_default:
        await db.execute(
            update(Template).where(Template.id != template_id).values(is_default=False)
        )

    # Update fields
    update_data = template_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    await db.flush()
    await db.refresh(template)

    logger.info(f"Updated template: {template.name}")
    return template


@router.delete("/{template_id}")
async def delete_template(template_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a template."""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    await db.delete(template)
    logger.info(f"Deleted template: {template.name}")
    return {"message": "Template deleted"}


@router.post("/{template_id}/preview")
async def preview_template(
    template_id: int,
    preview_data: TemplatePreview,
    db: AsyncSession = Depends(get_db),
):
    """Preview a template with sample data."""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        formatted = template.format_message(
            name=preview_data.name,
            company=preview_data.company,
        )
        return {"preview": formatted}
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Template has invalid placeholder: {e}"
        )


@router.get("/default/current", response_model=TemplateResponse)
async def get_default_template(db: AsyncSession = Depends(get_db)):
    """Get the current default template."""
    result = await db.execute(
        select(Template).where(Template.is_default == True)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="No default template set")

    return template
