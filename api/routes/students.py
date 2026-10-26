"""Student management routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.schemas import Student as StudentSchema
from database.connection import get_db
from database.crud import (
    create_student,
    get_student,
    get_students,
    search_students,
    update_student,
)

router = APIRouter(prefix="/students", tags=["students"])


class StudentRequest(BaseModel):
    """Student create/update request."""
    
    student_id: str
    name: str
    cgpa: float | None = None
    branch: str | None = None
    backlogs: int | None = None
    has_prior_offer: bool | None = None
    tenth_pct: float | None = None
    twelfth_pct: float | None = None


class StudentResponse(BaseModel):
    """Student information response."""
    
    student_id: str
    name: str
    cgpa: float | None
    branch: str | None
    backlogs: int | None
    has_prior_offer: bool | None
    tenth_pct: float | None
    twelfth_pct: float | None
    
    class Config:
        from_attributes = True


@router.post("", response_model=StudentResponse, status_code=201)
async def create_student_endpoint(
    request: StudentRequest,
    db: Session = Depends(get_db),
):
    """Create a new student.
    
    Args:
        request: Student data
        db: Database session
    
    Returns:
        Created student
    """
    # Check if student already exists
    existing = get_student(db, request.student_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Student with this ID already exists",
        )
    
    student_schema = StudentSchema(**request.model_dump())
    student = create_student(db, student_schema)
    
    return StudentResponse.model_validate(student)


@router.get("", response_model=list[StudentResponse])
async def list_students(
    branch: str | None = None,
    min_cgpa: float | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List students with optional filters.
    
    Args:
        branch: Optional filter by branch
        min_cgpa: Optional filter by minimum CGPA
        skip: Number of records to skip
        limit: Maximum records to return
        db: Database session
    
    Returns:
        List of students
    """
    if branch or min_cgpa is not None:
        students = search_students(db, branch=branch, min_cgpa=min_cgpa)
    else:
        students = get_students(db, skip=skip, limit=limit)
    
    return [StudentResponse.model_validate(s) for s in students]


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student_endpoint(
    student_id: str,
    db: Session = Depends(get_db),
):
    """Get student by ID.
    
    Args:
        student_id: Student identifier
        db: Database session
    
    Returns:
        Student information
    """
    student = get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    return StudentResponse.model_validate(student)


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student_endpoint(
    student_id: str,
    updates: dict,
    db: Session = Depends(get_db),
):
    """Update student information.
    
    Args:
        student_id: Student identifier
        updates: Fields to update
        db: Database session
    
    Returns:
        Updated student
    """
    student = update_student(db, student_id, updates)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    return StudentResponse.model_validate(student)
