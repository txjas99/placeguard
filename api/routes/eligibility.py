"""Eligibility checking routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.schemas import (
    Criterion,
    EligibilityResult,
    EligibilityStatus,
    Student as StudentSchema,
)
from database.connection import get_db
from database.crud import get_current_criteria, get_drive, get_student
from explanation.generator import generate_explanation_with_citations
from rules.eligibility_engine import check_eligibility

router = APIRouter(prefix="/eligibility", tags=["eligibility"])


class EligibilityCheckRequest(BaseModel):
    """Request to check student eligibility."""
    
    student_id: str
    drive_id: str
    generate_explanation: bool = True


class CriterionResultResponse(BaseModel):
    """Criterion check result."""
    
    criterion_type: str
    operator: str
    value: str
    scope: str
    status: str
    student_value: str | None
    message: str


class EligibilityCheckResponse(BaseModel):
    """Eligibility check result with explanation."""
    
    student_id: str
    drive_id: str
    status: str
    explanation: str | None
    summary: str | None
    criteria_results: list[CriterionResultResponse]
    criteria_checked: int
    criteria_passed: int
    criteria_failed: int
    criteria_unknown: int


@router.post("/check", response_model=EligibilityCheckResponse)
async def check_eligibility_endpoint(
    request: EligibilityCheckRequest,
    db: Session = Depends(get_db),
):
    """Check if a student is eligible for a drive.
    
    This endpoint:
    1. Retrieves student profile
    2. Gets current drive criteria (reconciled)
    3. Runs deterministic eligibility check
    4. Optionally generates LLM explanation
    
    Args:
        request: Eligibility check request
        db: Database session
    
    Returns:
        Eligibility result with optional explanation
    """
    # Get student
    student_db = get_student(db, request.student_id)
    if not student_db:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get drive
    drive = get_drive(db, request.drive_id)
    if not drive:
        raise HTTPException(status_code=404, detail="Drive not found")
    
    # Get current criteria
    criteria_db = get_current_criteria(db, request.drive_id)
    if not criteria_db:
        raise HTTPException(
            status_code=404,
            detail="No criteria found for this drive. Ingest a notice first.",
        )
    
    # Convert to schema objects
    student = StudentSchema(
        student_id=student_db.student_id,
        name=student_db.name,
        cgpa=student_db.cgpa,
        branch=student_db.branch,
        backlogs=student_db.backlogs,
        has_prior_offer=student_db.has_prior_offer,
        tenth_pct=student_db.tenth_pct,
        twelfth_pct=student_db.twelfth_pct,
    )
    
    criteria = []
    for c in criteria_db:
        # Parse value from JSON string
        import json
        value = json.loads(c.value)
        
        criteria.append(
            Criterion(
                drive_id=c.drive_id,
                criterion_type=c.criterion_type,
                operator=c.operator,
                value=value,
                scope=c.scope,
            )
        )
    
    # Check eligibility
    result = check_eligibility(student, criteria)
    
    # Generate explanation if requested
    explanation = None
    summary = None
    explanation_data = None
    
    if request.generate_explanation:
        try:
            explanation_data = generate_explanation_with_citations(result)
            explanation = explanation_data["explanation"]
            summary = explanation_data["summary"]
        except Exception as e:
            # Don't fail the request if explanation generation fails
            explanation = f"(Explanation generation failed: {str(e)})"
            summary = "Eligibility determined, but explanation unavailable."
    
    # Build response
    criteria_results_response = [
        CriterionResultResponse(
            criterion_type=cr.criterion.criterion_type,
            operator=cr.criterion.operator,
            value=str(cr.criterion.value),
            scope=cr.criterion.scope,
            status=cr.status.value,
            student_value=str(cr.student_value) if cr.student_value is not None else None,
            message=cr.message,
        )
        for cr in result.criterion_results
    ]
    
    return EligibilityCheckResponse(
        student_id=result.student_id,
        drive_id=result.drive_id,
        status=result.status.value,
        explanation=explanation,
        summary=summary,
        criteria_results=criteria_results_response,
        criteria_checked=len(result.criterion_results),
        criteria_passed=sum(1 for cr in result.criterion_results if cr.status.value == "PASS"),
        criteria_failed=sum(1 for cr in result.criterion_results if cr.status.value == "FAIL"),
        criteria_unknown=sum(1 for cr in result.criterion_results if cr.status.value == "UNKNOWN"),
    )
