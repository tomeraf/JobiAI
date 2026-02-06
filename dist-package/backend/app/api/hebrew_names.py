"""API endpoints for Hebrew name translations."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.hebrew_name import HebrewName
from app.services.hebrew_names import (
    translate_name_to_hebrew,
    save_hebrew_name,
    get_missing_hebrew_names,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class HebrewNameCreate(BaseModel):
    """Create a Hebrew name translation."""
    english_name: str
    hebrew_name: str


class HebrewNameResponse(BaseModel):
    """Response for a Hebrew name."""
    id: int
    english_name: str
    hebrew_name: str

    class Config:
        from_attributes = True


class HebrewNameBulkCreate(BaseModel):
    """Create multiple Hebrew name translations at once."""
    names: list[HebrewNameCreate]


class MissingNamesRequest(BaseModel):
    """Request to check which names are missing Hebrew translations."""
    names: list[str]


class MissingNamesResponse(BaseModel):
    """Response with list of names needing translations."""
    missing: list[str]


@router.post("", response_model=HebrewNameResponse)
async def create_hebrew_name(
    name_data: HebrewNameCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a Hebrew name translation.

    This saves a mapping from an English name to its Hebrew equivalent.
    Used when the bot encounters a name not in the built-in dictionary.
    """
    if not name_data.english_name or not name_data.hebrew_name:
        raise HTTPException(status_code=400, detail="Both english_name and hebrew_name are required")

    entry = await save_hebrew_name(
        english_name=name_data.english_name,
        hebrew_name=name_data.hebrew_name,
        db=db,
    )
    await db.commit()
    return entry


@router.post("/bulk", response_model=list[HebrewNameResponse])
async def create_hebrew_names_bulk(
    bulk_data: HebrewNameBulkCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Add multiple Hebrew name translations at once.

    This is useful when the workflow pauses with multiple unknown names.
    """
    if not bulk_data.names:
        raise HTTPException(status_code=400, detail="names list cannot be empty")

    results = []
    for name_data in bulk_data.names:
        if not name_data.english_name or not name_data.hebrew_name:
            continue
        entry = await save_hebrew_name(
            english_name=name_data.english_name,
            hebrew_name=name_data.hebrew_name,
            db=db,
        )
        results.append(entry)

    await db.commit()
    return results


@router.get("", response_model=list[HebrewNameResponse])
async def list_hebrew_names(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List all user-defined Hebrew name translations."""
    result = await db.execute(
        select(HebrewName)
        .order_by(HebrewName.english_name)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{english_name}")
async def get_hebrew_translation(
    english_name: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the Hebrew translation for an English name.

    Checks both the built-in dictionary and user-defined translations.
    Returns null if no translation is found.
    """
    hebrew = await translate_name_to_hebrew(english_name, db)
    return {
        "english_name": english_name.lower(),
        "hebrew_name": hebrew,
        "found": hebrew is not None,
    }


@router.post("/check-missing", response_model=MissingNamesResponse)
async def check_missing_names(
    request: MissingNamesRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Check which names from a list are missing Hebrew translations.

    This is used by the workflow to determine if it needs to pause
    and ask the user for translations before sending messages.
    """
    missing = await get_missing_hebrew_names(request.names, db)
    return MissingNamesResponse(missing=missing)


@router.delete("/{name_id}")
async def delete_hebrew_name(
    name_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a user-defined Hebrew name translation."""
    result = await db.execute(
        select(HebrewName).where(HebrewName.id == name_id)
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Hebrew name not found")

    await db.delete(entry)
    await db.commit()
    return {"message": "Hebrew name deleted"}
