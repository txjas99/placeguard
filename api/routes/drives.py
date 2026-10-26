"""Drive management routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import get_db
from database.crud import (
    create_drive,
    get_current_criteria,
    get_drive,
    get_drives,
)

router = APIRouter(prefix="/drives", tags=["drives"])


class DriveResponse(BaseModel):
    """Drive information response."""
    
    drive_id: str
    company_name: str
    status: str
    deadline: datetime | None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CriterionResponse(BaseModel):
    """Extracted criterion response."""
    
    criterion_type: str
    operator: str
    value: str
    scope: str
    source_type: str
    authority_rank: int
    timestamp: datetime
    
    class Config:
        from_attributes = True


class DriveWithCriteriaResponse(BaseModel):
    """Drive with current criteria."""
    
    drive: DriveResponse
    criteria: list[CriterionResponse]
    total_criteria: int


@router.get("", response_model=list[DriveResponse])
async def list_drives(
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List all placement drives.
    
    Args:
        status: Optional filter by status (active, closed, cancelled)
        skip: Number of records to skip
        limit: Maximum records to return
        db: Database session
    
    Returns:
        List of drives
    """
    drives = get_drives(db, status=status, skip=skip, limit=limit)
    return [DriveResponse.model_validate(d) for d in drives]


@router.get("/{drive_id}", response_model=DriveWithCriteriaResponse)
async def get_drive_details(
    drive_id: str,
    db: Session = Depends(get_db),
):
    """Get drive details with current criteria.
    
    Args:
        drive_id: Drive identifier
        db: Database session
    
    Returns:
        Drive with current reconciled criteria
    """
    drive = get_drive(db, drive_id)
    if not drive:
        raise HTTPException(status_code=404, detail="Drive not found")
    
    criteria = get_current_criteria(db, drive_id)
    
    return DriveWithCriteriaResponse(
        drive=DriveResponse.model_validate(drive),
        criteria=[CriterionResponse.model_validate(c) for c in criteria],
        total_criteria=len(criteria),
    )


@router.get("/{drive_id}/criteria", response_model=list[CriterionResponse])
async def get_drive_criteria(
    drive_id: str,
    db: Session = Depends(get_db),
):
    """Get current criteria for a drive.
    
    Args:
        drive_id: Drive identifier
        db: Database session
    
    Returns:
        List of current reconciled criteria
    """
    drive = get_drive(db, drive_id)
    if not drive:
        raise HTTPException(status_code=404, detail="Drive not found")
    
    criteria = get_current_criteria(db, drive_id)
    return [CriterionResponse.model_validate(c) for c in criteria]
