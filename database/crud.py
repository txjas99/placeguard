"""CRUD operations for PlaceGuard database.

Key principles:
- Facts are append-only (insert only, never update/delete)
- Students and Drives support full CRUD
- ExtractedCriteria are managed by reconciliation engine
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from core.schemas import Student as StudentSchema
from database.models import Drive, ExtractedCriterion, Fact, Student, utcnow


# ============================================================================
# STUDENT OPERATIONS
# ============================================================================

def create_student(db: Session, student: StudentSchema) -> Student:
    """Create a new student record."""
    db_student = Student(
        student_id=student.student_id,
        name=student.name,
        cgpa=student.cgpa,
        branch=student.branch,
        backlogs=student.backlogs,
        has_prior_offer=student.has_prior_offer,
        tenth_pct=student.tenth_pct,
        twelfth_pct=student.twelfth_pct,
    )
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student


def get_student(db: Session, student_id: str) -> Student | None:
    """Retrieve a student by ID."""
    return db.query(Student).filter(Student.student_id == student_id).first()


def get_students(
    db: Session, skip: int = 0, limit: int = 100
) -> List[Student]:
    """List all students with pagination."""
    return db.query(Student).offset(skip).limit(limit).all()


def update_student(
    db: Session, student_id: str, updates: dict
) -> Student | None:
    """Update student fields."""
    db_student = get_student(db, student_id)
    if not db_student:
        return None
    
    for key, value in updates.items():
        if hasattr(db_student, key):
            setattr(db_student, key, value)
    
    db_student.updated_at = utcnow()
    db.commit()
    db.refresh(db_student)
    return db_student


def delete_student(db: Session, student_id: str) -> bool:
    """Delete a student record."""
    db_student = get_student(db, student_id)
    if not db_student:
        return False
    
    db.delete(db_student)
    db.commit()
    return True


def search_students(
    db: Session, branch: str | None = None, min_cgpa: float | None = None
) -> List[Student]:
    """Search students by criteria."""
    query = db.query(Student)
    
    if branch:
        query = query.filter(Student.branch == branch)
    if min_cgpa is not None:
        query = query.filter(Student.cgpa >= min_cgpa)
    
    return query.all()


# ============================================================================
# DRIVE OPERATIONS
# ============================================================================

def create_drive(
    db: Session,
    drive_id: str,
    company_name: str,
    deadline: datetime | None = None,
    status: str = "active",
) -> Drive:
    """Create a new placement drive."""
    db_drive = Drive(
        drive_id=drive_id,
        company_name=company_name,
        deadline=deadline,
        status=status,
    )
    db.add(db_drive)
    db.commit()
    db.refresh(db_drive)
    return db_drive


def get_drive(db: Session, drive_id: str) -> Drive | None:
    """Retrieve a drive by ID."""
    return db.query(Drive).filter(Drive.drive_id == drive_id).first()


def get_drives(
    db: Session, status: str | None = None, skip: int = 0, limit: int = 100
) -> List[Drive]:
    """List drives with optional status filter."""
    query = db.query(Drive)
    
    if status:
        query = query.filter(Drive.status == status)
    
    return query.offset(skip).limit(limit).all()


def update_drive(
    db: Session, drive_id: str, updates: dict
) -> Drive | None:
    """Update drive fields."""
    db_drive = get_drive(db, drive_id)
    if not db_drive:
        return None
    
    for key, value in updates.items():
        if hasattr(db_drive, key):
            setattr(db_drive, key, value)
    
    db_drive.updated_at = utcnow()
    db.commit()
    db.refresh(db_drive)
    return db_drive


# ============================================================================
# FACT OPERATIONS (APPEND-ONLY)
# ============================================================================

def insert_fact(
    db: Session,
    source_id: str,
    source_type: str,
    authority_rank: int,
    timestamp: datetime,
    drive_id: str,
    criterion_type: str,
    operator: str,
    value: str,
    scope: str = "ALL",
    effective_timestamp: datetime | None = None,
    is_correction: bool = False,
    supersedes_ref: str | None = None,
    raw_notice_text: str | None = None,
) -> Fact:
    """Insert a new fact (NEVER update or delete).
    
    This is the only write operation allowed on the facts table.
    """
    if effective_timestamp is None:
        effective_timestamp = timestamp
    
    db_fact = Fact(
        source_id=source_id,
        source_type=source_type,
        authority_rank=authority_rank,
        timestamp=timestamp,
        effective_timestamp=effective_timestamp,
        drive_id=drive_id,
        criterion_type=criterion_type,
        operator=operator,
        value=value,
        scope=scope,
        is_correction=is_correction,
        supersedes_ref=supersedes_ref,
        raw_notice_text=raw_notice_text,
    )
    db.add(db_fact)
    db.commit()
    db.refresh(db_fact)
    return db_fact


def get_facts_by_drive(db: Session, drive_id: str) -> List[Fact]:
    """Retrieve all facts for a drive."""
    return db.query(Fact).filter(Fact.drive_id == drive_id).all()


def get_facts_by_rule_key(
    db: Session, drive_id: str, criterion_type: str, scope: str = "ALL"
) -> List[Fact]:
    """Retrieve all facts matching a rule key (drive_id, criterion_type, scope).
    
    This is the input to the reconciliation engine for determining current value.
    """
    return (
        db.query(Fact)
        .filter(
            and_(
                Fact.drive_id == drive_id,
                Fact.criterion_type == criterion_type,
                Fact.scope == scope,
            )
        )
        .order_by(Fact.authority_rank, Fact.effective_timestamp.desc())
        .all()
    )


def get_fact_by_source(db: Session, source_id: str) -> List[Fact]:
    """Retrieve all facts from a specific source."""
    return db.query(Fact).filter(Fact.source_id == source_id).all()


# ============================================================================
# EXTRACTED CRITERIA OPERATIONS (MANAGED BY RECONCILIATION ENGINE)
# ============================================================================

def upsert_extracted_criterion(
    db: Session,
    drive_id: str,
    criterion_type: str,
    operator: str,
    value: str,
    source_id: str,
    source_type: str,
    authority_rank: int,
    timestamp: datetime,
    scope: str = "ALL",
) -> ExtractedCriterion:
    """Insert or update the current extracted criterion for a rule key.
    
    This is called by the reconciliation engine after determining the
    current value via authority ranking and temporal logic.
    """
    # Check if criterion already exists
    existing = (
        db.query(ExtractedCriterion)
        .filter(
            and_(
                ExtractedCriterion.drive_id == drive_id,
                ExtractedCriterion.criterion_type == criterion_type,
                ExtractedCriterion.scope == scope,
            )
        )
        .first()
    )
    
    if existing:
        # Update existing
        existing.operator = operator
        existing.value = value
        existing.source_id = source_id
        existing.source_type = source_type
        existing.authority_rank = authority_rank
        existing.timestamp = timestamp
        existing.is_current = True
        existing.reconciled_at = utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Insert new
        criterion = ExtractedCriterion(
            drive_id=drive_id,
            criterion_type=criterion_type,
            scope=scope,
            operator=operator,
            value=value,
            source_id=source_id,
            source_type=source_type,
            authority_rank=authority_rank,
            timestamp=timestamp,
            is_current=True,
        )
        db.add(criterion)
        db.commit()
        db.refresh(criterion)
        return criterion


def get_current_criteria(
    db: Session, drive_id: str
) -> List[ExtractedCriterion]:
    """Retrieve all current criteria for a drive."""
    return (
        db.query(ExtractedCriterion)
        .filter(
            and_(
                ExtractedCriterion.drive_id == drive_id,
                ExtractedCriterion.is_current == True,
            )
        )
        .all()
    )


def get_criterion_by_type(
    db: Session, drive_id: str, criterion_type: str, scope: str = "ALL"
) -> ExtractedCriterion | None:
    """Retrieve a specific current criterion."""
    return (
        db.query(ExtractedCriterion)
        .filter(
            and_(
                ExtractedCriterion.drive_id == drive_id,
                ExtractedCriterion.criterion_type == criterion_type,
                ExtractedCriterion.scope == scope,
                ExtractedCriterion.is_current == True,
            )
        )
        .first()
    )
