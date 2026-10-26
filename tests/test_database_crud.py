"""Tests for database CRUD operations."""

from datetime import datetime

import pytest

from core.schemas import Student as StudentSchema
from database import crud
from database.connection import get_db_context, init_db


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Initialize database before running tests."""
    init_db()


def test_create_and_get_student():
    """Test creating and retrieving a student."""
    with get_db_context() as db:
        # Create student
        student_data = StudentSchema(
            student_id="test_s1",
            name="Test Student",
            cgpa=8.5,
            branch="CSE",
            backlogs=0,
            has_prior_offer=False,
            tenth_pct=85.0,
            twelfth_pct=88.0,
        )
        
        created = crud.create_student(db, student_data)
        assert created.student_id == "test_s1"
        assert created.cgpa == 8.5
        
        # Retrieve student
        retrieved = crud.get_student(db, "test_s1")
        assert retrieved is not None
        assert retrieved.name == "Test Student"
        assert retrieved.branch == "CSE"
        
        # Cleanup
        crud.delete_student(db, "test_s1")


def test_update_student():
    """Test updating student fields."""
    with get_db_context() as db:
        # Create student
        student_data = StudentSchema(
            student_id="test_s2",
            name="Update Test",
            cgpa=7.5,
            branch="ISE",
        )
        crud.create_student(db, student_data)
        
        # Update
        updated = crud.update_student(
            db, "test_s2", {"cgpa": 8.0, "backlogs": 1}
        )
        assert updated.cgpa == 8.0
        assert updated.backlogs == 1
        
        # Cleanup
        crud.delete_student(db, "test_s2")


def test_create_drive():
    """Test creating a placement drive."""
    with get_db_context() as db:
        drive = crud.create_drive(
            db,
            drive_id="test_drive_1",
            company_name="Test Company",
            deadline=datetime(2026, 11, 1, 18, 0),
        )
        
        assert drive.drive_id == "test_drive_1"
        assert drive.company_name == "Test Company"
        assert drive.status == "active"
        
        # Retrieve
        retrieved = crud.get_drive(db, "test_drive_1")
        assert retrieved is not None
        assert retrieved.company_name == "Test Company"


def test_insert_fact():
    """Test inserting a fact (append-only)."""
    with get_db_context() as db:
        fact = crud.insert_fact(
            db,
            source_id="test_source_1",
            source_type="placement_cell_whatsapp",
            authority_rank=2,
            timestamp=datetime(2026, 10, 26, 10, 0),
            drive_id="test_drive_1",
            criterion_type="min_cgpa",
            operator="gte",
            value="7.5",
            raw_notice_text="Minimum CGPA: 7.5",
        )
        
        assert fact.id is not None
        assert fact.drive_id == "test_drive_1"
        assert fact.criterion_type == "min_cgpa"
        assert fact.value == "7.5"
        
        # Retrieve
        facts = crud.get_facts_by_drive(db, "test_drive_1")
        assert len(facts) >= 1
        assert any(f.criterion_type == "min_cgpa" for f in facts)


def test_get_facts_by_rule_key():
    """Test retrieving facts by rule key."""
    with get_db_context() as db:
        # Insert multiple facts for same rule key
        crud.insert_fact(
            db,
            source_id="test_source_2a",
            source_type="student_whatsapp",
            authority_rank=5,
            timestamp=datetime(2026, 10, 26, 9, 0),
            drive_id="test_drive_2",
            criterion_type="min_cgpa",
            operator="gte",
            value="7.0",
        )
        
        crud.insert_fact(
            db,
            source_id="test_source_2b",
            source_type="placement_cell_whatsapp",
            authority_rank=2,
            timestamp=datetime(2026, 10, 26, 10, 0),
            drive_id="test_drive_2",
            criterion_type="min_cgpa",
            operator="gte",
            value="7.5",
        )
        
        # Retrieve by rule key
        facts = crud.get_facts_by_rule_key(
            db, drive_id="test_drive_2", criterion_type="min_cgpa"
        )
        
        assert len(facts) == 2
        # Should be ordered by authority_rank, then timestamp DESC
        assert facts[0].authority_rank <= facts[1].authority_rank


def test_upsert_extracted_criterion():
    """Test upserting extracted criteria."""
    with get_db_context() as db:
        # Insert new criterion
        criterion = crud.upsert_extracted_criterion(
            db,
            drive_id="test_drive_3",
            criterion_type="min_cgpa",
            operator="gte",
            value="7.5",
            source_id="test_source_3",
            source_type="placement_cell_whatsapp",
            authority_rank=2,
            timestamp=datetime(2026, 10, 26, 10, 0),
        )
        
        assert criterion.id is not None
        assert criterion.value == "7.5"
        
        # Update same criterion
        updated = crud.upsert_extracted_criterion(
            db,
            drive_id="test_drive_3",
            criterion_type="min_cgpa",
            operator="gte",
            value="8.0",
            source_id="test_source_3b",
            source_type="official_company_pdf",
            authority_rank=1,
            timestamp=datetime(2026, 10, 26, 11, 0),
        )
        
        assert updated.id == criterion.id  # Same record
        assert updated.value == "8.0"  # Updated value
        
        # Verify only one record exists
        criteria = crud.get_current_criteria(db, "test_drive_3")
        assert len(criteria) == 1
