"""Unit tests for reconciliation engine.

Tests authority ranking, temporal logic, supersession handling, and coverage fallback.
"""

from datetime import datetime

import pytest

from database.models import Fact
from reconciliation.temporal_provenance_engine import (
    RuleKey,
    _reconcile_fact_group,
    get_reconciliation_trace,
    reconcile_facts,
    reconcile_with_coverage_fallback,
)


class TestRuleKey:
    """Test RuleKey dataclass behavior."""
    
    def test_rule_key_equality(self):
        """Test that rule keys with same values are equal."""
        key1 = RuleKey(drive_id="drive_001", criterion_type="min_cgpa", scope="ALL")
        key2 = RuleKey(drive_id="drive_001", criterion_type="min_cgpa", scope="ALL")
        
        assert key1 == key2
        assert hash(key1) == hash(key2)
    
    def test_rule_key_inequality_different_drive(self):
        """Test that rule keys with different drives are not equal."""
        key1 = RuleKey(drive_id="drive_001", criterion_type="min_cgpa")
        key2 = RuleKey(drive_id="drive_002", criterion_type="min_cgpa")
        
        assert key1 != key2
    
    def test_rule_key_inequality_different_type(self):
        """Test that rule keys with different criterion types are not equal."""
        key1 = RuleKey(drive_id="drive_001", criterion_type="min_cgpa")
        key2 = RuleKey(drive_id="drive_001", criterion_type="max_backlogs")
        
        assert key1 != key2
    
    def test_rule_key_inequality_different_scope(self):
        """Test that rule keys with different scopes are not equal."""
        key1 = RuleKey(drive_id="drive_001", criterion_type="min_cgpa", scope="CSE")
        key2 = RuleKey(drive_id="drive_001", criterion_type="min_cgpa", scope="ISE")
        
        assert key1 != key2


class TestSameAuthorityLatestWins:
    """Test that among same authority rank, latest timestamp wins."""
    
    def test_same_rank_later_timestamp_wins(self):
        """Test later timestamp wins among same authority rank."""
        facts = [
            Fact(
                source_id="email_001",
                source_type="placement_cell_email",
                authority_rank=2,
                timestamp=datetime(2026, 10, 26, 10, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 10, 0, 0),
                drive_id="drive_001",
                criterion_type="min_cgpa",
                scope="ALL",
                operator="gte",
                value='"7.0"',
                is_correction=False,
            ),
            Fact(
                source_id="email_002",
                source_type="placement_cell_email",
                authority_rank=2,
                timestamp=datetime(2026, 10, 26, 12, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 12, 0, 0),
                drive_id="drive_001",
                criterion_type="min_cgpa",
                scope="ALL",
                operator="gte",
                value='"7.5"',
                is_correction=False,
            ),
        ]
        
        result = _reconcile_fact_group(facts)
        
        assert result.source_id == "email_002"
        assert result.value == '"7.5"'
        assert result.timestamp == datetime(2026, 10, 26, 12, 0, 0)
    
    def test_effective_timestamp_used(self):
        """Test that effective_timestamp is used for temporal ordering."""
        facts = [
            Fact(
                source_id="email_001",
                source_type="placement_cell_email",
                authority_rank=2,
                timestamp=datetime(2026, 10, 26, 10, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 16, 0, 0),  # Effective later
                drive_id="drive_001",
                criterion_type="deadline",
                scope="ALL",
                operator="eq",
                value='"2026-10-30T18:00:00"',
                is_correction=False,
            ),
            Fact(
                source_id="email_002",
                source_type="placement_cell_email",
                authority_rank=2,
                timestamp=datetime(2026, 10, 26, 14, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 14, 0, 0),  # Effective earlier
                drive_id="drive_001",
                criterion_type="deadline",
                scope="ALL",
                operator="eq",
                value='"2026-10-30T16:00:00"',
                is_correction=False,
            ),
        ]
        
        result = _reconcile_fact_group(facts)
        
        # email_001 wins because its effective_timestamp is later
        assert result.source_id == "email_001"
        assert result.value == '"2026-10-30T18:00:00"'


class TestHigherAuthorityOverrides:
    """Test that higher authority rank always wins regardless of timestamp."""
    
    def test_official_beats_student_forward(self):
        """Test official PDF (rank 1) beats student forward (rank 5) regardless of time."""
        facts = [
            Fact(
                source_id="student_whatsapp_001",
                source_type="student_whatsapp",
                authority_rank=5,
                timestamp=datetime(2026, 10, 26, 16, 0, 0),  # Later
                effective_timestamp=datetime(2026, 10, 26, 16, 0, 0),
                drive_id="drive_001",
                criterion_type="min_cgpa",
                scope="ALL",
                operator="gte",
                value='"7.0"',
                is_correction=False,
            ),
            Fact(
                source_id="official_pdf_001",
                source_type="official_company_pdf",
                authority_rank=1,
                timestamp=datetime(2026, 10, 26, 8, 0, 0),  # Earlier
                effective_timestamp=datetime(2026, 10, 26, 8, 0, 0),
                drive_id="drive_001",
                criterion_type="min_cgpa",
                scope="ALL",
                operator="gte",
                value='"7.5"',
                is_correction=False,
            ),
        ]
        
        result = _reconcile_fact_group(facts)
        
        # Official PDF wins despite being earlier
        assert result.source_id == "official_pdf_001"
        assert result.value == '"7.5"'
        assert result.authority_rank == 1
    
    def test_placement_cell_beats_coordinator(self):
        """Test placement cell (rank 2) beats coordinator (rank 3)."""
        facts = [
            Fact(
                source_id="coordinator_msg",
                source_type="coordinator_whatsapp",
                authority_rank=3,
                timestamp=datetime(2026, 10, 26, 14, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 14, 0, 0),
                drive_id="drive_002",
                criterion_type="max_backlogs",
                scope="ALL",
                operator="lte",
                value='"2"',
                is_correction=False,
            ),
            Fact(
                source_id="placement_email",
                source_type="placement_cell_email",
                authority_rank=2,
                timestamp=datetime(2026, 10, 26, 9, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 9, 0, 0),
                drive_id="drive_002",
                criterion_type="max_backlogs",
                scope="ALL",
                operator="eq",
                value='"0"',
                is_correction=False,
            ),
        ]
        
        result = _reconcile_fact_group(facts)
        
        assert result.source_id == "placement_email"
        assert result.value == '"0"'


class TestExplicitSupersession:
    """Test handling of explicit supersession via is_correction flag."""
    
    def test_correction_flag_takes_precedence(self):
        """Test that is_correction=True takes precedence over timestamp."""
        facts = [
            Fact(
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
            ),
            Fact(
                source_id="email_002",
                source_type="placement_cell_email",
                authority_rank=2,
                timestamp=datetime(2026, 10, 26, 11, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 11, 0, 0),
                drive_id="drive_001",
                criterion_type="min_cgpa",
                scope="ALL",
                operator="gte",
                value='"7.0"',
                is_correction=True,  # Marked as correction
                supersedes_ref="email_001",
            ),
        ]
        
        result = _reconcile_fact_group(facts)
        
        assert result.source_id == "email_002"
        assert result.value == '"7.0"'
        assert result.is_correction is True
    
    def test_latest_correction_wins_among_corrections(self):
        """Test that among multiple corrections, latest wins."""
        facts = [
            Fact(
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
            ),
            Fact(
                source_id="email_002",
                source_type="placement_cell_email",
                authority_rank=2,
                timestamp=datetime(2026, 10, 26, 11, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 11, 0, 0),
                drive_id="drive_001",
                criterion_type="min_cgpa",
                scope="ALL",
                operator="gte",
                value='"7.0"',
                is_correction=True,
            ),
            Fact(
                source_id="email_003",
                source_type="placement_cell_email",
                authority_rank=2,
                timestamp=datetime(2026, 10, 26, 12, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 12, 0, 0),
                drive_id="drive_001",
                criterion_type="min_cgpa",
                scope="ALL",
                operator="gte",
                value='"7.2"',
                is_correction=True,
            ),
        ]
        
        result = _reconcile_fact_group(facts)
        
        # Latest correction (email_003) wins
        assert result.source_id == "email_003"
        assert result.value == '"7.2"'


class TestCoverageFallback:
    """Test coverage fallback: lower authority fills gaps, doesn't override."""
    
    def test_different_criteria_dont_conflict(self):
        """Test that different criterion types don't interfere."""
        facts = [
            Fact(
                source_id="official_pdf",
                source_type="official_company_pdf",
                authority_rank=1,
                timestamp=datetime(2026, 10, 26, 8, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 8, 0, 0),
                drive_id="drive_001",
                criterion_type="min_cgpa",
                scope="ALL",
                operator="gte",
                value='"7.5"',
                is_correction=False,
            ),
            Fact(
                source_id="whatsapp_msg",
                source_type="placement_cell_whatsapp",
                authority_rank=2,
                timestamp=datetime(2026, 10, 26, 10, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 10, 0, 0),
                drive_id="drive_001",
                criterion_type="allowed_branches",
                scope="ALL",
                operator="in",
                value='"CSE,ISE"',
                is_correction=False,
            ),
        ]
        
        result = reconcile_facts(facts)
        
        # Both criteria should be present (different rule keys)
        assert len(result) == 2
        
        cgpa_key = RuleKey("drive_001", "min_cgpa", "ALL")
        branch_key = RuleKey("drive_001", "allowed_branches", "ALL")
        
        assert result[cgpa_key].source_id == "official_pdf"
        assert result[branch_key].source_id == "whatsapp_msg"

    def test_coverage_fallback_via_named_function(self):
        """reconcile_with_coverage_fallback fills gaps without overriding (DESIGN 3.1 step 4).

        Official PDF asserts min_cgpa (rank 1); placement-cell WhatsApp asserts a
        different rule_key (allowed_branches, rank 2). The named coverage-fallback
        entry point must keep BOTH: CGPA from the PDF (no override) and branches from
        WhatsApp (coverage gap fill).
        """
        facts = [
            Fact(
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
            ),
            Fact(
                source_id="whatsapp_msg",
                source_type="placement_cell_whatsapp",
                authority_rank=2,
                timestamp=datetime(2026, 10, 26, 10, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 10, 0, 0),
                drive_id="drive_001",
                criterion_type="allowed_branches",
                scope="ALL",
                operator="in",
                value='"CSE,ISE"',
                is_correction=False,
            ),
        ]

        result = reconcile_with_coverage_fallback(facts)

        assert len(result) == 2
        cgpa_key = RuleKey("drive_001", "min_cgpa", "ALL")
        branch_key = RuleKey("drive_001", "allowed_branches", "ALL")
        assert result[cgpa_key].source_id == "official_pdf"     # higher authority kept
        assert result[cgpa_key].authority_rank == 1
        assert result[branch_key].source_id == "whatsapp_msg"  # coverage gap filled
        assert result[branch_key].authority_rank == 2

    def test_coverage_fallback_never_overrides_higher_authority(self):
        """Lower authority asserting the SAME rule_key must not override higher authority."""
        facts = [
            # Official PDF: CGPA 7.5 (rank 1)
            Fact(
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
            ),
            # WhatsApp: CGPA 7.0 (rank 2, same rule_key) - must NOT override
            Fact(
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
            ),
        ]

        result = reconcile_with_coverage_fallback(facts)

        assert len(result) == 1
        key = RuleKey("drive_001", "min_cgpa", "ALL")
        # Higher authority (PDF) wins - lower authority does not override
        assert result[key].source_id == "official_pdf"
        assert result[key].value == '"7.5"'
        assert result[key].authority_rank == 1


class TestMultipleConflicts:
    """Test complex scenarios with multiple conflicting facts."""
    
    def test_multiple_sources_multiple_ranks(self):
        """Test reconciliation with facts from multiple sources at different ranks."""
        facts = [
            # Official PDF - rank 1
            Fact(
                source_id="pdf_001",
                source_type="official_company_pdf",
                authority_rank=1,
                timestamp=datetime(2026, 10, 25, 8, 0, 0),
                effective_timestamp=datetime(2026, 10, 25, 8, 0, 0),
                drive_id="drive_001",
                criterion_type="min_cgpa",
                scope="ALL",
                operator="gte",
                value='"8.0"',
                is_correction=False,
            ),
            # Placement cell email - rank 2 (earlier)
            Fact(
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
            ),
            # Placement cell email - rank 2 (later)
            Fact(
                source_id="email_002",
                source_type="placement_cell_email",
                authority_rank=2,
                timestamp=datetime(2026, 10, 26, 14, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 14, 0, 0),
                drive_id="drive_001",
                criterion_type="min_cgpa",
                scope="ALL",
                operator="gte",
                value='"7.0"',
                is_correction=False,
            ),
            # Student WhatsApp - rank 5
            Fact(
                source_id="student_msg",
                source_type="student_whatsapp",
                authority_rank=5,
                timestamp=datetime(2026, 10, 26, 16, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 16, 0, 0),
                drive_id="drive_001",
                criterion_type="min_cgpa",
                scope="ALL",
                operator="gte",
                value='"6.5"',
                is_correction=False,
            ),
        ]
        
        result = _reconcile_fact_group(facts)
        
        # Official PDF (rank 1) should win
        assert result.source_id == "pdf_001"
        assert result.value == '"8.0"'
        assert result.authority_rank == 1
    
    def test_multiple_drives_reconciled_separately(self):
        """Test that facts from different drives don't interfere."""
        facts = [
            Fact(
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
            ),
            Fact(
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
            ),
        ]
        
        result = reconcile_facts(facts)
        
        # Should have 2 rule keys (different drives)
        assert len(result) == 2
        
        key1 = RuleKey("drive_001", "min_cgpa", "ALL")
        key2 = RuleKey("drive_002", "min_cgpa", "ALL")
        
        assert result[key1].value == '"7.5"'
        assert result[key2].value == '"8.0"'


class TestReconciliationTrace:
    """Test reconciliation trace generation for debugging."""
    
    def test_trace_shows_all_sources(self):
        """Test that trace includes information about all facts considered."""
        facts = [
            Fact(
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
            ),
            Fact(
                source_id="student_msg",
                source_type="student_whatsapp",
                authority_rank=5,
                timestamp=datetime(2026, 10, 26, 12, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 12, 0, 0),
                drive_id="drive_001",
                criterion_type="min_cgpa",
                scope="ALL",
                operator="gte",
                value='"7.0"',
                is_correction=False,
            ),
        ]
        
        trace = get_reconciliation_trace(facts)
        
        assert trace["total_facts"] == 2
        assert trace["unique_rule_keys"] == 1
        assert len(trace["reconciliation_details"]) == 1
        
        detail = trace["reconciliation_details"][0]
        assert detail["total_facts"] == 2
        assert detail["authority_ranks_present"] == [2, 5]
        assert detail["selected_authority_rank"] == 2
        assert detail["winner_source"] == "email_001"
        assert "email_001" in detail["all_sources"]
        assert "student_msg" in detail["all_sources"]


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_fact_list(self):
        """Test reconciliation with empty fact list."""
        result = reconcile_facts([])
        assert len(result) == 0
    
    def test_single_fact(self):
        """Test reconciliation with single fact."""
        facts = [
            Fact(
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
            ),
        ]
        
        result = reconcile_facts(facts)
        
        assert len(result) == 1
        key = RuleKey("drive_001", "min_cgpa", "ALL")
        assert result[key].source_id == "email_001"
    
    def test_scoped_criteria_separate_rule_keys(self):
        """Test that same criterion type with different scopes creates separate rule keys."""
        facts = [
            Fact(
                source_id="email_001",
                source_type="placement_cell_email",
                authority_rank=2,
                timestamp=datetime(2026, 10, 26, 10, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 10, 0, 0),
                drive_id="drive_001",
                criterion_type="min_cgpa",
                scope="CSE",
                operator="gte",
                value='"8.0"',
                is_correction=False,
            ),
            Fact(
                source_id="email_001",
                source_type="placement_cell_email",
                authority_rank=2,
                timestamp=datetime(2026, 10, 26, 10, 0, 0),
                effective_timestamp=datetime(2026, 10, 26, 10, 0, 0),
                drive_id="drive_001",
                criterion_type="min_cgpa",
                scope="ISE",
                operator="gte",
                value='"7.5"',
                is_correction=False,
            ),
        ]
        
        result = reconcile_facts(facts)
        
        # Should have 2 separate rule keys due to different scopes
        assert len(result) == 2
        
        key_cse = RuleKey("drive_001", "min_cgpa", "CSE")
        key_ise = RuleKey("drive_001", "min_cgpa", "ISE")
        
        assert result[key_cse].value == '"8.0"'
        assert result[key_ise].value == '"7.5"'
