"""Unit tests for notice extraction module.

Tests LLM-based criteria extraction, supersession detection, and error handling.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from core.schemas import SourceType
from extraction.notice_extractor import (
    detect_supersession_explicit,
    extract_criteria_from_notice,
    extract_with_confidence,
)


class MockLLMClient:
    """Mock LLM client for testing without real API calls."""
    
    def __init__(self, response_data=None):
        self.response_data = response_data or []
        self.calls = []
    
    def generate_structured(self, prompt, schema=None, temperature=None):
        """Mock structured generation."""
        self.calls.append({
            "prompt": prompt,
            "schema": schema,
            "temperature": temperature,
        })
        return self.response_data


class TestExtractCleanNotice:
    """Test extraction from well-formatted notices."""
    
    def test_extract_basic_criteria(self):
        """Test extraction of basic eligibility criteria."""
        notice_text = """
        TechCorp Placement Drive
        
        Eligibility:
        - Minimum CGPA: 7.5
        - Branches: CSE, ISE only
        - No active backlogs
        
        Deadline: October 30, 2026
        """
        
        mock_response = [
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
            {
                "criterion_type": "max_backlogs",
                "operator": "eq",
                "value": "0",
                "scope": "ALL",
                "confidence": "high",
                "is_correction": False,
                "supersedes_ref": None,
                "notes": "",
            },
        ]
        
        mock_llm = MockLLMClient(response_data=mock_response)
        
        facts = extract_criteria_from_notice(
            notice_text=notice_text,
            source_id="test_001",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_001",
            llm_client=mock_llm,
        )
        
        assert len(facts) == 3
        assert facts[0].criterion_type == "min_cgpa"
        assert facts[0].operator == "gte"
        assert facts[0].value == '"7.5"'  # JSON serialized
        assert facts[0].authority_rank == 2  # Placement cell email
        assert facts[0].drive_id == "drive_001"
        assert facts[0].source_id == "test_001"
    
    def test_extract_with_scope(self):
        """Test extraction with scoped criteria (branch-specific)."""
        notice_text = """
        DataCorp Drive
        
        For CSE: Minimum CGPA 8.0
        For ISE: Minimum CGPA 7.5
        For other branches: Minimum CGPA 7.0
        """
        
        mock_response = [
            {
                "criterion_type": "min_cgpa",
                "operator": "gte",
                "value": "8.0",
                "scope": "CSE",
                "confidence": "high",
                "is_correction": False,
                "supersedes_ref": None,
                "notes": "",
            },
            {
                "criterion_type": "min_cgpa",
                "operator": "gte",
                "value": "7.5",
                "scope": "ISE",
                "confidence": "high",
                "is_correction": False,
                "supersedes_ref": None,
                "notes": "",
            },
        ]
        
        mock_llm = MockLLMClient(response_data=mock_response)
        
        facts = extract_criteria_from_notice(
            notice_text=notice_text,
            source_id="test_002",
            source_type=SourceType.PLACEMENT_CELL_WHATSAPP,
            timestamp=datetime(2026, 10, 26, 11, 0, 0),
            drive_id="drive_002",
            llm_client=mock_llm,
        )
        
        assert len(facts) == 2
        assert facts[0].scope == "CSE"
        assert facts[1].scope == "ISE"


class TestDetectSupersession:
    """Test supersession and correction detection."""
    
    def test_detect_deadline_update(self):
        """Test detection of deadline extension."""
        notice_text = """
        Update: Registration deadline extended to 6PM from 4PM.
        """
        
        mock_response = [
            {
                "criterion_type": "deadline",
                "operator": "eq",
                "value": "2026-10-30T18:00:00",
                "scope": "ALL",
                "confidence": "high",
                "is_correction": True,
                "supersedes_ref": None,
                "notes": "Deadline extended from 4PM",
            },
        ]
        
        mock_llm = MockLLMClient(response_data=mock_response)
        
        facts = extract_criteria_from_notice(
            notice_text=notice_text,
            source_id="test_003",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 15, 0, 0),
            drive_id="drive_001",
            llm_client=mock_llm,
        )
        
        assert len(facts) == 1
        assert facts[0].is_correction is True
        assert "deadline" in facts[0].criterion_type
    
    def test_detect_correction_marker(self):
        """Test detection of explicit correction."""
        notice_text = """
        Correction: The minimum CGPA is 7.5, not 7.0 as stated earlier.
        """
        
        mock_response = [
            {
                "criterion_type": "min_cgpa",
                "operator": "gte",
                "value": "7.5",
                "scope": "ALL",
                "confidence": "high",
                "is_correction": True,
                "supersedes_ref": "email_001",
                "notes": "Corrects previous notice",
            },
        ]
        
        mock_llm = MockLLMClient(response_data=mock_response)
        
        facts = extract_criteria_from_notice(
            notice_text=notice_text,
            source_id="test_004",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 12, 0, 0),
            drive_id="drive_001",
            llm_client=mock_llm,
        )
        
        assert len(facts) == 1
        assert facts[0].is_correction is True
        assert facts[0].supersedes_ref == "email_001"
    
    def test_explicit_supersession_detection_correction(self):
        """Test keyword-based supersession detection for corrections."""
        notice_text = "Correction: CGPA requirement is 7.5"
        
        result = detect_supersession_explicit(notice_text)
        
        assert result["is_supersession"] is True
        assert result["supersession_type"] == "correction"
        assert result["confidence"] == "high"
    
    def test_explicit_supersession_detection_update(self):
        """Test keyword-based supersession detection for updates."""
        notice_text = "Update: Branch list has been revised to include ECE"
        
        result = detect_supersession_explicit(notice_text)
        
        assert result["is_supersession"] is True
        assert result["supersession_type"] == "update"
    
    def test_explicit_supersession_detection_extension(self):
        """Test keyword-based supersession detection for extensions."""
        notice_text = "Deadline extended to November 1st"
        
        result = detect_supersession_explicit(notice_text)
        
        assert result["is_supersession"] is True
        assert result["supersession_type"] == "extension"
    
    def test_no_supersession_detected(self):
        """Test no supersession in regular notice."""
        notice_text = "Regular placement notice with criteria"
        
        result = detect_supersession_explicit(notice_text)
        
        assert result["is_supersession"] is False
        assert result["supersession_type"] is None


class TestHandleMissingFields:
    """Test handling of incomplete or missing information."""
    
    def test_handle_empty_notice(self):
        """Test extraction from empty notice returns no facts."""
        notice_text = ""
        
        mock_response = []  # LLM returns empty list
        mock_llm = MockLLMClient(response_data=mock_response)
        
        facts = extract_criteria_from_notice(
            notice_text=notice_text,
            source_id="test_005",
            source_type=SourceType.STUDENT_WHATSAPP,
            timestamp=datetime(2026, 10, 26, 14, 0, 0),
            drive_id="drive_003",
            llm_client=mock_llm,
        )
        
        assert len(facts) == 0
    
    def test_handle_incomplete_criteria(self):
        """Test extraction skips items with missing required fields."""
        notice_text = "Some criteria here"
        
        mock_response = [
            {
                "criterion_type": "min_cgpa",
                "operator": "gte",
                "value": "7.5",
            },
            {
                "criterion_type": "max_backlogs",
                # Missing operator and value
            },
        ]
        
        mock_llm = MockLLMClient(response_data=mock_response)
        
        facts = extract_criteria_from_notice(
            notice_text=notice_text,
            source_id="test_006",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_004",
            llm_client=mock_llm,
        )
        
        # Only the complete criterion should be extracted
        assert len(facts) == 1
        assert facts[0].criterion_type == "min_cgpa"
    
    def test_handle_dict_response_instead_of_list(self):
        """Test extraction handles dict response (wraps in list)."""
        notice_text = "Single criterion notice"
        
        # LLM returns single dict instead of list
        mock_response = {
            "criterion_type": "min_cgpa",
            "operator": "gte",
            "value": "7.0",
            "scope": "ALL",
            "confidence": "high",
            "is_correction": False,
            "supersedes_ref": None,
            "notes": "",
        }
        
        mock_llm = MockLLMClient(response_data=mock_response)
        
        facts = extract_criteria_from_notice(
            notice_text=notice_text,
            source_id="test_007",
            source_type=SourceType.COORDINATOR_WHATSAPP,
            timestamp=datetime(2026, 10, 26, 13, 0, 0),
            drive_id="drive_005",
            llm_client=mock_llm,
        )
        
        assert len(facts) == 1
        assert facts[0].criterion_type == "min_cgpa"


class TestAmbiguousRequirements:
    """Test handling of ambiguous or unclear criteria."""
    
    def test_extract_ambiguous_with_note(self):
        """Test extraction marks ambiguous criteria with low confidence."""
        notice_text = """
        Good academic record required.
        Strong performance expected.
        """
        
        mock_response = [
            {
                "criterion_type": "min_cgpa",
                "operator": "gte",
                "value": "7.0",
                "scope": "ALL",
                "confidence": "low",
                "is_correction": False,
                "supersedes_ref": None,
                "notes": "Ambiguous: 'good academic record' - inferred as 7.0 CGPA",
            },
        ]
        
        mock_llm = MockLLMClient(response_data=mock_response)
        
        facts = extract_criteria_from_notice(
            notice_text=notice_text,
            source_id="test_008",
            source_type=SourceType.STUDENT_WHATSAPP,
            timestamp=datetime(2026, 10, 26, 16, 0, 0),
            drive_id="drive_006",
            llm_client=mock_llm,
        )
        
        assert len(facts) == 1
        # Note: confidence is not stored in Fact model currently
        # but could be added to raw_notice_text or a metadata field


class TestAuthorityRanking:
    """Test that facts get correct authority rank based on source type."""
    
    def test_official_pdf_highest_rank(self):
        """Test official company PDF gets rank 1."""
        mock_response = [
            {"criterion_type": "min_cgpa", "operator": "gte", "value": "7.5"}
        ]
        mock_llm = MockLLMClient(response_data=mock_response)
        
        facts = extract_criteria_from_notice(
            notice_text="CGPA 7.5 required",
            source_id="pdf_001",
            source_type=SourceType.OFFICIAL_COMPANY_PDF,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_007",
            llm_client=mock_llm,
        )
        
        assert facts[0].authority_rank == 1
    
    def test_placement_cell_email_rank_2(self):
        """Test placement cell email gets rank 2."""
        mock_response = [
            {"criterion_type": "min_cgpa", "operator": "gte", "value": "7.5"}
        ]
        mock_llm = MockLLMClient(response_data=mock_response)
        
        facts = extract_criteria_from_notice(
            notice_text="CGPA 7.5 required",
            source_id="email_001",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_007",
            llm_client=mock_llm,
        )
        
        assert facts[0].authority_rank == 2
    
    def test_student_whatsapp_lowest_rank(self):
        """Test student WhatsApp gets rank 5 (lowest)."""
        mock_response = [
            {"criterion_type": "min_cgpa", "operator": "gte", "value": "7.5"}
        ]
        mock_llm = MockLLMClient(response_data=mock_response)
        
        facts = extract_criteria_from_notice(
            notice_text="CGPA 7.5 required",
            source_id="whatsapp_123",
            source_type=SourceType.STUDENT_WHATSAPP,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_007",
            llm_client=mock_llm,
        )
        
        assert facts[0].authority_rank == 5


class TestErrorHandling:
    """Test error handling for extraction failures."""
    
    def test_invalid_llm_response_raises_error(self):
        """Test that invalid LLM response raises ValueError."""
        mock_llm = MockLLMClient(response_data="invalid string response")
        
        with pytest.raises(ValueError, match="Expected list"):
            extract_criteria_from_notice(
                notice_text="Some notice",
                source_id="test_009",
                source_type=SourceType.PLACEMENT_CELL_EMAIL,
                timestamp=datetime(2026, 10, 26, 10, 0, 0),
                drive_id="drive_008",
                llm_client=mock_llm,
            )
    
    def test_llm_client_exception_propagates(self):
        """Test that LLM client exceptions are properly handled."""
        mock_llm = Mock()
        mock_llm.generate_structured.side_effect = Exception("API timeout")
        
        with pytest.raises(ValueError, match="Failed to extract criteria"):
            extract_criteria_from_notice(
                notice_text="Some notice",
                source_id="test_010",
                source_type=SourceType.PLACEMENT_CELL_EMAIL,
                timestamp=datetime(2026, 10, 26, 10, 0, 0),
                drive_id="drive_009",
                llm_client=mock_llm,
            )


class TestProvenanceTracking:
    """Test that extracted facts preserve full provenance information."""
    
    def test_fact_preserves_raw_notice(self):
        """Test that raw notice text is stored in fact."""
        notice_text = "Original notice text with criteria"
        
        mock_response = [
            {"criterion_type": "min_cgpa", "operator": "gte", "value": "7.5"}
        ]
        mock_llm = MockLLMClient(response_data=mock_response)
        
        facts = extract_criteria_from_notice(
            notice_text=notice_text,
            source_id="test_011",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_010",
            llm_client=mock_llm,
        )
        
        assert facts[0].raw_notice_text == notice_text
    
    def test_fact_preserves_timestamp(self):
        """Test that timestamp is correctly preserved."""
        timestamp = datetime(2026, 10, 26, 14, 30, 0)
        
        mock_response = [
            {"criterion_type": "min_cgpa", "operator": "gte", "value": "7.5"}
        ]
        mock_llm = MockLLMClient(response_data=mock_response)
        
        facts = extract_criteria_from_notice(
            notice_text="CGPA requirement",
            source_id="test_012",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=timestamp,
            drive_id="drive_011",
            llm_client=mock_llm,
        )
        
        assert facts[0].timestamp == timestamp
        assert facts[0].effective_timestamp == timestamp  # Default


class TestConfidenceFiltering:
    """Test confidence-based filtering in extract_with_confidence().

    Covers Task 2 known issue: confidence filtering was previously a no-op stub.
    """

    @staticmethod
    def _mixed_confidence_response():
        return [
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
                "criterion_type": "max_backlogs",
                "operator": "eq",
                "value": "0",
                "scope": "ALL",
                "confidence": "medium",
                "is_correction": False,
                "supersedes_ref": None,
                "notes": "",
            },
            {
                "criterion_type": "min_tenth_pct",
                "operator": "gte",
                "value": "60",
                "scope": "ALL",
                "confidence": "low",
                "is_correction": False,
                "supersedes_ref": None,
                "notes": "Ambiguous requirement",
            },
        ]

    def test_default_threshold_accepts_high_and_medium(self):
        """Default min_confidence='medium' accepts high and medium, rejects low."""
        mock_llm = MockLLMClient(response_data=self._mixed_confidence_response())

        accepted, low_conf = extract_with_confidence(
            notice_text="Some notice",
            source_id="conf_001",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_001",
            llm_client=mock_llm,
        )

        assert len(accepted) == 2
        assert {f.criterion_type for f in accepted} == {"min_cgpa", "max_backlogs"}
        assert len(low_conf) == 1
        assert low_conf[0]["criterion_type"] == "min_tenth_pct"
        assert low_conf[0]["confidence"] == "low"

    def test_high_threshold_rejects_medium_and_low(self):
        """min_confidence='high' accepts only high-confidence facts."""
        mock_llm = MockLLMClient(response_data=self._mixed_confidence_response())

        accepted, low_conf = extract_with_confidence(
            notice_text="Some notice",
            source_id="conf_002",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_001",
            llm_client=mock_llm,
            min_confidence="high",
        )

        assert len(accepted) == 1
        assert accepted[0].criterion_type == "min_cgpa"
        assert len(low_conf) == 2
        assert {item["criterion_type"] for item in low_conf} == {
            "max_backlogs",
            "min_tenth_pct",
        }

    def test_low_threshold_accepts_all(self):
        """min_confidence='low' accepts all facts; no low-confidence items."""
        mock_llm = MockLLMClient(response_data=self._mixed_confidence_response())

        accepted, low_conf = extract_with_confidence(
            notice_text="Some notice",
            source_id="conf_003",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_001",
            llm_client=mock_llm,
            min_confidence="low",
        )

        assert len(accepted) == 3
        assert len(low_conf) == 0

    def test_low_confidence_items_are_descriptive(self):
        """Low-confidence review items carry criterion details and a reason."""
        mock_llm = MockLLMClient(response_data=self._mixed_confidence_response())

        _, low_conf = extract_with_confidence(
            notice_text="Some notice",
            source_id="conf_004",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_001",
            llm_client=mock_llm,
        )

        item = low_conf[0]
        assert set(item.keys()) >= {
            "criterion_type",
            "operator",
            "value",
            "scope",
            "confidence",
            "notes",
            "reason",
        }
        assert item["notes"] == "Ambiguous requirement"
        assert "below the minimum threshold" in item["reason"]

    def test_missing_confidence_defaults_to_high(self):
        """Items omitting confidence default to high and are accepted at medium threshold."""
        mock_response = [
            {"criterion_type": "min_cgpa", "operator": "gte", "value": "7.5"},
        ]
        mock_llm = MockLLMClient(response_data=mock_response)

        accepted, low_conf = extract_with_confidence(
            notice_text="Some notice",
            source_id="conf_005",
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            timestamp=datetime(2026, 10, 26, 10, 0, 0),
            drive_id="drive_001",
            llm_client=mock_llm,
        )

        assert len(accepted) == 1
        assert len(low_conf) == 0
