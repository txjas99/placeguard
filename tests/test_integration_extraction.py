"""Integration tests for the full extraction and reconciliation pipeline.

Tests end-to-end scenarios from raw notices through extraction to reconciliation.
"""

from datetime import datetime
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.schemas import SourceType
from database.crud import (
    create_drive,
    get_current_criteria,
    insert_fact,
)
from database.models import Base, Fact
from extraction.notice_extractor import extract_criteria_from_notice
from reconciliation.temporal_provenance_engine import (
    RuleKey,
    reconcile_facts,
    reconcile_facts_for_drive,
)


@pytest.fixture
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    yield db
    
    db.close()


@pytest.fixture
def mock_llm():
    """Create mock LLM client for testing."""
    mock = Mock()
    mock.generate_structured = Mock()
    return mock


class TestEndToEndPipeline:
    """Test complete pipeline: notice → extract → store → reconcile → query."""
    
    def test_single_notice_extraction_and_storage(self, test_db, mock_llm):
        """Test extracting and storing criteria from a single notice."""
        # Setup
        create_drive(test_db, "drive_001", "TechCorp")
        
        notice_text = """
        TechCorp Placement Drive
        Eligibility: CGPA 7.5+, CSE/ISE only, no backlogs
        """
        
        # Mock LLM response
        mock_llm.generate_structured.return_value = [
            {
                "criterion_type": "min_cgpa",
                "operator": "gte",
                "value": "7.5",
                "scope": "ALL",
                "confidence": "high",
                "is_correction": False,
                "supersedes_ref": None,
                "notes": "",
            },
            {
                "criterion_type": "allowed_branches",
                "operator": "in",
                "value": "CSE,ISE",
                "scope": "ALL",
                "confidence": "high",
                "is_correction": False,
                "supersedes_ref": None,
                "notes": "",
            },
        ]
        
        # Extract
        facts = extract_criteria_from_notice(
            notice_text=notice_text,
            source_id="email_001",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_001",
            llm_client=mock_llm,
        )
        
        # Store
        for fact in facts:
            test_db.add(fact)
        test_db.commit()
        
        # Reconcile and persist
        reconciled = reconcile_facts_for_drive(test_db, "drive_001", persist=True)
        
        # Query current criteria
        current = get_current_criteria(test_db, "drive_001")
        
        # Assert
        assert len(current) == 2
        assert any(c.criterion_type == "min_cgpa" for c in current)
        assert any(c.criterion_type == "allowed_branches" for c in current)


class TestMultiSourceConflict:
    """Test reconciliation with conflicting information from multiple sources."""
    
    def test_same_authority_latest_wins(self, test_db):
        """Test that among same authority, latest timestamp wins."""
        create_drive(test_db, "drive_001", "TechCorp")
        
        # First email: CGPA 7.5
        fact1 = Fact(
            source_id="email_001",
            source_type="placement_cell_email",
            authority_rank=2,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            effective_timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_001",
            criterion_type="min_cgpa",
            scope="ALL",
            operator="gte",
            value='"7.5"',
            is_correction=False,
        )
        
        # Second email (later): CGPA 8.0
        fact2 = Fact(
            source_id="email_002",
            source_type="placement_cell_email",
            authority_rank=2,
            timestamp=datetime(2026, 10, 26, 14, 0, 0),
            effective_timestamp=datetime(2026, 10, 26, 14, 0, 0),
            drive_id="drive_001",
            criterion_type="min_cgpa",
            scope="ALL",
            operator="gte",
            value='"8.0"',
            is_correction=False,
        )
        
        test_db.add(fact1)
        test_db.add(fact2)
        test_db.commit()
        
        # Reconcile
        reconciled = reconcile_facts_for_drive(test_db, "drive_001", persist=True)
        
        # Query
        current = get_current_criteria(test_db, "drive_001")
        
        # Latest should win (8.0)
        assert len(current) == 1
        assert current[0].value == '"8.0"'
        assert current[0].source_id == "email_002"


class TestAuthorityOverride:
    """Test that higher authority overrides lower regardless of timestamp."""
    
    def test_official_pdf_beats_later_student_forward(self, test_db):
        """Test official PDF (rank 1) beats student forward (rank 5) even if later."""
        create_drive(test_db, "drive_001", "TechCorp")
        
        # Student forward (later, rank 5): CGPA 7.0
        fact1 = Fact(
            source_id="student_msg",
            source_type="student_whatsapp",
            authority_rank=5,
            timestamp=datetime(2026, 10, 26, 16, 0, 0),
            effective_timestamp=datetime(2026, 10, 26, 16, 0, 0),
            drive_id="drive_001",
            criterion_type="min_cgpa",
            scope="ALL",
            operator="gte",
            value='"7.0"',
            is_correction=False,
        )
        
        # Official PDF (earlier, rank 1): CGPA 7.5
        fact2 = Fact(
            source_id="official_pdf_001",
            source_type="official_company_pdf",
            authority_rank=1,
            timestamp=datetime(2026, 10, 25, 8, 0, 0),
            effective_timestamp=datetime(2026, 10, 25, 8, 0, 0),
            drive_id="drive_001",
            criterion_type="min_cgpa",
            scope="ALL",
            operator="gte",
            value='"7.5"',
            is_correction=False,
        )
        
        test_db.add(fact1)
        test_db.add(fact2)
        test_db.commit()
        
        # Reconcile
        reconciled = reconcile_facts_for_drive(test_db, "drive_001", persist=True)
        
        # Query
        current = get_current_criteria(test_db, "drive_001")
        
        # Official PDF should win (7.5)
        assert len(current) == 1
        assert current[0].value == '"7.5"'
        assert current[0].source_id == "official_pdf_001"
        assert current[0].authority_rank == 1


class TestDeadlineUpdate:
    """Test handling of deadline updates and extensions."""
    
    def test_deadline_extension_with_correction_flag(self, test_db):
        """Test deadline extension marked as correction."""
        create_drive(test_db, "drive_001", "TechCorp")
        
        # Original deadline
        fact1 = Fact(
            source_id="email_001",
            source_type="placement_cell_email",
            authority_rank=2,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            effective_timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_001",
            criterion_type="deadline",
            scope="ALL",
            operator="eq",
            value='"2026-10-30T16:00:00"',
            is_correction=False,
        )
        
        # Extension notice (correction)
        fact2 = Fact(
            source_id="email_002",
            source_type="placement_cell_email",
            authority_rank=2,
            timestamp=datetime(2026, 10, 26, 15, 0, 0),
            effective_timestamp=datetime(2026, 10, 26, 15, 0, 0),
            drive_id="drive_001",
            criterion_type="deadline",
            scope="ALL",
            operator="eq",
            value='"2026-10-30T18:00:00"',
            is_correction=True,  # Marked as extension
            supersedes_ref="email_001",
        )
        
        test_db.add(fact1)
        test_db.add(fact2)
        test_db.commit()
        
        # Reconcile
        reconciled = reconcile_facts_for_drive(test_db, "drive_001", persist=True)
        
        # Query
        current = get_current_criteria(test_db, "drive_001")
        
        # Extended deadline should win
        assert len(current) == 1
        assert current[0].value == '"2026-10-30T18:00:00"'
        assert current[0].source_id == "email_002"


class TestCoverageFallback:
    """Test coverage fallback: lower authority fills gaps but doesn't override."""
    
    def test_official_states_cgpa_whatsapp_adds_branch(self, test_db):
        """Test official PDF states CGPA, WhatsApp fills in branch info."""
        create_drive(test_db, "drive_001", "TechCorp")
        
        # Official PDF: Only CGPA (rank 1)
        fact1 = Fact(
            source_id="official_pdf",
            source_type="official_company_pdf",
            authority_rank=1,
            timestamp=datetime(2026, 10, 25, 8, 0, 0),
            effective_timestamp=datetime(2026, 10, 25, 8, 0, 0),
            drive_id="drive_001",
            criterion_type="min_cgpa",
            scope="ALL",
            operator="gte",
            value='"7.5"',
            is_correction=False,
        )
        
        # WhatsApp: States CGPA=7.0 AND branch=CSE (rank 2)
        fact2 = Fact(
            source_id="whatsapp_msg",
            source_type="placement_cell_whatsapp",
            authority_rank=2,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            effective_timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_001",
            criterion_type="min_cgpa",
            scope="ALL",
            operator="gte",
            value='"7.0"',
            is_correction=False,
        )
        
        fact3 = Fact(
            source_id="whatsapp_msg",
            source_type="placement_cell_whatsapp",
            authority_rank=2,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            effective_timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_001",
            criterion_type="allowed_branches",
            scope="ALL",
            operator="in",
            value='"CSE"',
            is_correction=False,
        )
        
        test_db.add_all([fact1, fact2, fact3])
        test_db.commit()
        
        # Reconcile
        reconciled = reconcile_facts_for_drive(test_db, "drive_001", persist=True)
        
        # Query
        current = get_current_criteria(test_db, "drive_001")
        
        # Should have CGPA from PDF (7.5) and branch from WhatsApp (CSE)
        assert len(current) == 2
        
        cgpa_criterion = next(c for c in current if c.criterion_type == "min_cgpa")
        branch_criterion = next(c for c in current if c.criterion_type == "allowed_branches")
        
        assert cgpa_criterion.value == '"7.5"'  # From official PDF (higher authority)
        assert cgpa_criterion.authority_rank == 1
        
        assert branch_criterion.value == '"CSE"'  # From WhatsApp (coverage)
        assert branch_criterion.authority_rank == 2


class TestMultipleDrives:
    """Test that reconciliation handles multiple drives independently."""
    
    def test_criteria_from_different_drives_dont_interfere(self, test_db):
        """Test that different drives maintain separate criteria."""
        create_drive(test_db, "drive_001", "TechCorp")
        create_drive(test_db, "drive_002", "DataCorp")
        
        # Drive 1: CGPA 7.5
        fact1 = Fact(
            source_id="email_drive1",
            source_type="placement_cell_email",
            authority_rank=2,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            effective_timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_001",
            criterion_type="min_cgpa",
            scope="ALL",
            operator="gte",
            value='"7.5"',
            is_correction=False,
        )
        
        # Drive 2: CGPA 8.0
        fact2 = Fact(
            source_id="email_drive2",
            source_type="placement_cell_email",
            authority_rank=2,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            effective_timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_002",
            criterion_type="min_cgpa",
            scope="ALL",
            operator="gte",
            value='"8.0"',
            is_correction=False,
        )
        
        test_db.add_all([fact1, fact2])
        test_db.commit()
        
        # Reconcile both drives
        reconciled_1 = reconcile_facts_for_drive(test_db, "drive_001", persist=True)
        reconciled_2 = reconcile_facts_for_drive(test_db, "drive_002", persist=True)
        
        # Query each drive
        current_1 = get_current_criteria(test_db, "drive_001")
        current_2 = get_current_criteria(test_db, "drive_002")
        
        # Each drive should have its own CGPA
        assert len(current_1) == 1
        assert len(current_2) == 1
        assert current_1[0].value == '"7.5"'
        assert current_2[0].value == '"8.0"'


class TestComplexScenario:
    """Test complex real-world scenario with multiple updates and sources."""
    
    def test_realistic_notice_sequence(self, test_db, mock_llm):
        """Test realistic sequence: initial notice → correction → extension → student forward."""
        create_drive(test_db, "drive_001", "TechCorp")
        
        # Scenario:
        # 1. Initial notice from placement cell: CGPA 7.5, deadline Oct 30 4PM
        # 2. Correction from placement cell: CGPA 7.0 (corrected)
        # 3. Extension from placement cell: deadline Oct 30 6PM
        # 4. Student forward (later): CGPA 6.5 (should be ignored)
        
        # Notice 1: Initial
        mock_llm.generate_structured.return_value = [
            {
                "criterion_type": "min_cgpa",
                "operator": "gte",
                "value": "7.5",
                "scope": "ALL",
                "confidence": "high",
                "is_correction": False,
                "supersedes_ref": None,
                "notes": "",
            },
            {
                "criterion_type": "deadline",
                "operator": "eq",
                "value": "2026-10-30T16:00:00",
                "scope": "ALL",
                "confidence": "high",
                "is_correction": False,
                "supersedes_ref": None,
                "notes": "",
            },
        ]
        
        facts1 = extract_criteria_from_notice(
            notice_text="CGPA 7.5, deadline Oct 30 4PM",
            source_id="email_001",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_001",
            llm_client=mock_llm,
        )
        
        for fact in facts1:
            test_db.add(fact)
        test_db.commit()
        
        # Notice 2: Correction
        mock_llm.generate_structured.return_value = [
            {
                "criterion_type": "min_cgpa",
                "operator": "gte",
                "value": "7.0",
                "scope": "ALL",
                "confidence": "high",
                "is_correction": True,
                "supersedes_ref": "email_001",
                "notes": "Corrected from 7.5",
            },
        ]
        
        facts2 = extract_criteria_from_notice(
            notice_text="Correction: CGPA is 7.0",
            source_id="email_002",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 12, 0, 0),
            drive_id="drive_001",
            llm_client=mock_llm,
        )
        
        for fact in facts2:
            test_db.add(fact)
        test_db.commit()
        
        # Notice 3: Extension
        mock_llm.generate_structured.return_value = [
            {
                "criterion_type": "deadline",
                "operator": "eq",
                "value": "2026-10-30T18:00:00",
                "scope": "ALL",
                "confidence": "high",
                "is_correction": True,
                "supersedes_ref": "email_001",
                "notes": "Extended from 4PM",
            },
        ]
        
        facts3 = extract_criteria_from_notice(
            notice_text="Deadline extended to 6PM",
            source_id="email_003",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 15, 0, 0),
            drive_id="drive_001",
            llm_client=mock_llm,
        )
        
        for fact in facts3:
            test_db.add(fact)
        test_db.commit()
        
        # Notice 4: Student forward (should be ignored)
        fact4 = Fact(
            source_id="student_msg",
            source_type="student_whatsapp",
            authority_rank=5,
            timestamp=datetime(2026, 10, 26, 18, 0, 0),
            effective_timestamp=datetime(2026, 10, 26, 18, 0, 0),
            drive_id="drive_001",
            criterion_type="min_cgpa",
            scope="ALL",
            operator="gte",
            value='"6.5"',
            is_correction=False,
        )
        test_db.add(fact4)
        test_db.commit()
        
        # Reconcile
        reconciled = reconcile_facts_for_drive(test_db, "drive_001", persist=True)
        
        # Query
        current = get_current_criteria(test_db, "drive_001")
        
        # Expected: CGPA 7.0 (corrected), deadline 6PM (extended)
        assert len(current) == 2
        
        cgpa = next(c for c in current if c.criterion_type == "min_cgpa")
        deadline = next(c for c in current if c.criterion_type == "deadline")
        
        assert cgpa.value == '"7.0"'
        assert cgpa.source_id == "email_002"
        assert deadline.value == '"2026-10-30T18:00:00"'
        assert deadline.source_id == "email_003"
