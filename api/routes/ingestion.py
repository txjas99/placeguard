"""Ingestion routes for notice processing."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.schemas import SourceType
from database.connection import get_db
from database.crud import create_drive, get_drive
from extraction.llm_client import get_llm_client
from extraction.notice_extractor import extract_criteria_from_notice
from reconciliation.temporal_provenance_engine import reconcile_facts_for_drive

router = APIRouter(prefix="/ingest", tags=["ingestion"])


class IngestNoticeRequest(BaseModel):
    """Request to ingest a placement notice."""
    
    notice_text: str
    source_id: str
    source_type: SourceType
    timestamp: datetime | None = None
    drive_id: str
    drive_name: str | None = None


class IngestNoticeResponse(BaseModel):
    """Response from notice ingestion."""
    
    success: bool
    drive_id: str
    facts_extracted: int
    criteria_reconciled: int
    message: str


@router.post("/notice", response_model=IngestNoticeResponse)
async def ingest_notice(
    request: IngestNoticeRequest,
    db: Session = Depends(get_db),
):
    """Ingest a placement notice and extract criteria.
    
    This endpoint:
    1. Creates drive if it doesn't exist
    2. Extracts criteria from notice text using LLM
    3. Stores facts in database
    4. Runs reconciliation to update current criteria
    
    Args:
        request: Notice ingestion request
        db: Database session
    
    Returns:
        Ingestion result with counts
    """
    try:
        # Ensure drive exists
        drive = get_drive(db, request.drive_id)
        if not drive:
            drive_name = request.drive_name or request.drive_id
            drive = create_drive(
                db,
                drive_id=request.drive_id,
                company_name=drive_name,
            )
        
        # Use current time if not provided
        timestamp = request.timestamp or datetime.utcnow()
        
        # Extract criteria from notice
        llm_client = get_llm_client()
        facts = extract_criteria_from_notice(
            notice_text=request.notice_text,
            source_id=request.source_id,
            source_type=request.source_type,
            timestamp=timestamp,
            drive_id=request.drive_id,
            llm_client=llm_client,
        )
        
        # Store facts in database
        for fact in facts:
            db.add(fact)
        db.commit()
        
        # Run reconciliation to update current criteria
        reconciled = reconcile_facts_for_drive(db, request.drive_id, persist=True)
        
        return IngestNoticeResponse(
            success=True,
            drive_id=request.drive_id,
            facts_extracted=len(facts),
            criteria_reconciled=len(reconciled),
            message=f"Successfully ingested notice and extracted {len(facts)} facts, reconciled to {len(reconciled)} current criteria",
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to ingest notice: {str(e)}",
        )
