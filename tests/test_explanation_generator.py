"""Unit tests for explanation generator.

Tests LLM-based explanation generation from eligibility results.
"""

from unittest.mock import Mock

import pytest

from core.schemas import (
    Criterion,
    CriterionResult,
    EligibilityResult,
    EligibilityStatus,
    Status,
)
from explanation.generator import (
    ExplanationGenerator,
    generate_explanation,
    generate_explanation_with_citations,
)


class MockLLMClient:
    """Mock LLM client for testing."""
    
    def __init__(self, response_text="Mock explanation text"):
        self.response_text = response_text
        self.calls = []
    
    def generate(self, prompt, temperature=None):
        """Mock generate method."""
        self.calls.append({
            "prompt": prompt,
            "temperature": temperature,
        })
        return self.response_text


class TestExplanationGenerator:
    """Test explanation generator functionality."""
    
    def test_generate_eligible_explanation(self):
        """Test explanation generation for eligible student."""
        # Setup
        result = EligibilityResult(
            student_id="s001",
            drive_id="drive_001",
            status=EligibilityStatus.ELIGIBLE,
            criterion_results=[
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="min_cgpa",
                        operator="gte",
                        value=7.5,
                        scope="ALL",
                    ),
                    status=Status.PASS,
                    student_value=8.0,
                    message="CGPA requirement met",
                ),
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="max_backlogs",
                        operator="lte",
                        value=0,
                        scope="ALL",
                    ),
                    status=Status.PASS,
                    student_value=0,
                    message="No backlogs",
                ),
            ],
        )
        
        mock_llm = MockLLMClient("You are eligible for this drive. All requirements met.")
        generator = ExplanationGenerator(mock_llm)
        
        # Execute
        explanation = generator.generate(result)
        
        # Assert
        assert explanation == "You are eligible for this drive. All requirements met."
        assert len(mock_llm.calls) == 1
        assert "ELIGIBLE" in mock_llm.calls[0]["prompt"]
        # Check for criterion (with or without underscore, case-insensitive)
        prompt_lower = mock_llm.calls[0]["prompt"].lower()
        assert "min" in prompt_lower and "cgpa" in prompt_lower
    
    def test_generate_ineligible_explanation(self):
        """Test explanation generation for ineligible student."""
        result = EligibilityResult(
            student_id="s002",
            drive_id="drive_001",
            status=EligibilityStatus.INELIGIBLE,
            criterion_results=[
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="min_cgpa",
                        operator="gte",
                        value=7.5,
                        scope="ALL",
                    ),
                    status=Status.FAIL,
                    student_value=7.0,
                    message="CGPA below minimum",
                ),
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="max_backlogs",
                        operator="lte",
                        value=0,
                        scope="ALL",
                    ),
                    status=Status.PASS,
                    student_value=0,
                    message="No backlogs",
                ),
            ],
        )
        
        mock_llm = MockLLMClient("You are not eligible. CGPA requirement not met.")
        generator = ExplanationGenerator(mock_llm)
        
        explanation = generator.generate(result)
        
        assert "not eligible" in explanation.lower()
        assert len(mock_llm.calls) == 1
    
    def test_generate_unknown_explanation(self):
        """Test explanation generation when information is missing."""
        result = EligibilityResult(
            student_id="s003",
            drive_id="drive_001",
            status=EligibilityStatus.UNKNOWN,
            criterion_results=[
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="min_cgpa",
                        operator="gte",
                        value=7.5,
                        scope="ALL",
                    ),
                    status=Status.UNKNOWN,
                    student_value=None,
                    message="CGPA information not available",
                ),
            ],
        )
        
        mock_llm = MockLLMClient("Eligibility cannot be determined. CGPA information missing.")
        generator = ExplanationGenerator(mock_llm)
        
        explanation = generator.generate(result)
        
        assert "cannot be determined" in explanation.lower() or "missing" in explanation.lower()
    
    def test_format_criterion_results(self):
        """Test criterion results formatting for prompt."""
        result = EligibilityResult(
            student_id="s001",
            drive_id="drive_001",
            status=EligibilityStatus.ELIGIBLE,
            criterion_results=[
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="min_cgpa",
                        operator="gte",
                        value=7.5,
                        scope="ALL",
                    ),
                    status=Status.PASS,
                    student_value=8.0,
                    message="Met requirement",
                ),
            ],
        )
        
        generator = ExplanationGenerator(MockLLMClient())
        formatted = generator._format_criterion_results(result.criterion_results)
        
        assert "Min Cgpa" in formatted
        assert "✓ PASS" in formatted
        assert "8.0" in formatted
        assert "gte 7.5" in formatted
    
    def test_format_criterion_with_scope(self):
        """Test formatting criterion with scope."""
        result = EligibilityResult(
            student_id="s001",
            drive_id="drive_001",
            status=EligibilityStatus.ELIGIBLE,
            criterion_results=[
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="min_cgpa",
                        operator="gte",
                        value=8.0,
                        scope="CSE",
                    ),
                    status=Status.PASS,
                    student_value=8.2,
                    message="Met CSE requirement",
                ),
            ],
        )
        
        generator = ExplanationGenerator(MockLLMClient())
        formatted = generator._format_criterion_results(result.criterion_results)
        
        assert "scope: CSE" in formatted


class TestGenerateSummary:
    """Test summary generation."""
    
    def test_summary_eligible(self):
        """Test summary for eligible student."""
        result = EligibilityResult(
            student_id="s001",
            drive_id="drive_001",
            status=EligibilityStatus.ELIGIBLE,
            criterion_results=[],
        )
        
        generator = ExplanationGenerator(MockLLMClient())
        summary = generator.generate_summary(result)
        
        assert "eligible" in summary.lower()
        assert "s001" in summary
        assert "drive_001" in summary
    
    def test_summary_ineligible_with_reasons(self):
        """Test summary for ineligible student with failure reasons."""
        result = EligibilityResult(
            student_id="s002",
            drive_id="drive_001",
            status=EligibilityStatus.INELIGIBLE,
            criterion_results=[
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="min_cgpa",
                        operator="gte",
                        value=7.5,
                    ),
                    status=Status.FAIL,
                    student_value=7.0,
                    message="Failed",
                ),
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="max_backlogs",
                        operator="lte",
                        value=0,
                    ),
                    status=Status.FAIL,
                    student_value=2,
                    message="Failed",
                ),
            ],
        )
        
        generator = ExplanationGenerator(MockLLMClient())
        summary = generator.generate_summary(result)
        
        assert "not eligible" in summary.lower()
        assert "min_cgpa" in summary or "max_backlogs" in summary
    
    def test_summary_unknown(self):
        """Test summary for unknown status."""
        result = EligibilityResult(
            student_id="s003",
            drive_id="drive_001",
            status=EligibilityStatus.UNKNOWN,
            criterion_results=[],
        )
        
        generator = ExplanationGenerator(MockLLMClient())
        summary = generator.generate_summary(result)
        
        assert "cannot be determined" in summary.lower() or "missing" in summary.lower()


class TestGenerateWithCitations:
    """Test explanation generation with citations."""
    
    def test_generate_with_citations_structure(self):
        """Test that generate_with_citations returns proper structure."""
        result = EligibilityResult(
            student_id="s001",
            drive_id="drive_001",
            status=EligibilityStatus.ELIGIBLE,
            criterion_results=[
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="min_cgpa",
                        operator="gte",
                        value=7.5,
                        scope="ALL",
                    ),
                    status=Status.PASS,
                    student_value=8.0,
                    message="Met requirement",
                ),
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="max_backlogs",
                        operator="lte",
                        value=0,
                        scope="ALL",
                    ),
                    status=Status.PASS,
                    student_value=0,
                    message="No backlogs",
                ),
            ],
        )
        
        mock_llm = MockLLMClient("Full explanation text")
        generator = ExplanationGenerator(mock_llm)
        
        output = generator.generate_with_citations(result)
        
        # Check structure
        assert "explanation" in output
        assert "summary" in output
        assert "status" in output
        assert "citations" in output
        assert "criteria_checked" in output
        assert "criteria_passed" in output
        assert "criteria_failed" in output
        assert "criteria_unknown" in output
        
        # Check values
        assert output["status"] == "ELIGIBLE"
        assert output["student_id"] == "s001"
        assert output["drive_id"] == "drive_001"
        assert output["criteria_checked"] == 2
        assert output["criteria_passed"] == 2
        assert output["criteria_failed"] == 0
        assert output["criteria_unknown"] == 0
    
    def test_citations_extraction(self):
        """Test that citations are properly extracted."""
        result = EligibilityResult(
            student_id="s001",
            drive_id="drive_001",
            status=EligibilityStatus.ELIGIBLE,
            criterion_results=[
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="min_cgpa",
                        operator="gte",
                        value=7.5,
                        scope="CSE",
                    ),
                    status=Status.PASS,
                    student_value=8.0,
                    message="Met",
                ),
            ],
        )
        
        generator = ExplanationGenerator(MockLLMClient())
        output = generator.generate_with_citations(result)
        
        assert len(output["citations"]) == 1
        assert output["citations"][0]["criterion_type"] == "min_cgpa"
        assert output["citations"][0]["scope"] == "CSE"
    
    def test_mixed_status_counts(self):
        """Test criteria counts with mixed statuses."""
        result = EligibilityResult(
            student_id="s001",
            drive_id="drive_001",
            status=EligibilityStatus.INELIGIBLE,
            criterion_results=[
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="min_cgpa",
                        operator="gte",
                        value=7.5,
                    ),
                    status=Status.FAIL,
                    student_value=7.0,
                    message="Failed",
                ),
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="max_backlogs",
                        operator="lte",
                        value=0,
                    ),
                    status=Status.PASS,
                    student_value=0,
                    message="Passed",
                ),
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="min_tenth_pct",
                        operator="gte",
                        value=60,
                    ),
                    status=Status.UNKNOWN,
                    student_value=None,
                    message="Unknown",
                ),
            ],
        )
        
        generator = ExplanationGenerator(MockLLMClient())
        output = generator.generate_with_citations(result)
        
        assert output["criteria_checked"] == 3
        assert output["criteria_passed"] == 1
        assert output["criteria_failed"] == 1
        assert output["criteria_unknown"] == 1


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_generate_explanation_function(self):
        """Test generate_explanation convenience function."""
        result = EligibilityResult(
            student_id="s001",
            drive_id="drive_001",
            status=EligibilityStatus.ELIGIBLE,
            criterion_results=[],
        )
        
        mock_llm = MockLLMClient("Test explanation")
        explanation = generate_explanation(result, mock_llm)
        
        assert explanation == "Test explanation"
    
    def test_generate_explanation_with_citations_function(self):
        """Test generate_explanation_with_citations convenience function."""
        result = EligibilityResult(
            student_id="s001",
            drive_id="drive_001",
            status=EligibilityStatus.ELIGIBLE,
            criterion_results=[],
        )
        
        mock_llm = MockLLMClient("Test explanation")
        output = generate_explanation_with_citations(result, mock_llm)
        
        assert "explanation" in output
        assert "summary" in output
        assert output["explanation"] == "Test explanation"


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_criterion_results(self):
        """Test handling of empty criterion results."""
        result = EligibilityResult(
            student_id="s001",
            drive_id="drive_001",
            status=EligibilityStatus.UNKNOWN,
            criterion_results=[],
        )
        
        generator = ExplanationGenerator(MockLLMClient())
        formatted = generator._format_criterion_results([])
        
        assert "No criteria were evaluated" in formatted
    
    def test_criterion_without_student_value(self):
        """Test formatting criterion when student value is None."""
        result = EligibilityResult(
            student_id="s001",
            drive_id="drive_001",
            status=EligibilityStatus.UNKNOWN,
            criterion_results=[
                CriterionResult(
                    criterion=Criterion(
                        drive_id="drive_001",
                        criterion_type="min_cgpa",
                        operator="gte",
                        value=7.5,
                    ),
                    status=Status.UNKNOWN,
                    student_value=None,
                    message="Value not available",
                ),
            ],
        )
        
        generator = ExplanationGenerator(MockLLMClient())
        formatted = generator._format_criterion_results(result.criterion_results)
        
        # Should not crash and should show status
        assert "? UNKNOWN" in formatted
        assert "not available" in formatted.lower()
