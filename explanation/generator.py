"""Explanation generator for eligibility decisions.

Uses LLM to generate natural language explanations from structured eligibility results,
with proper citation of evidence sources. Implements DESIGN.md principle: "GenAI explains,
deterministic engine decides."
"""

from __future__ import annotations

from typing import Any

from core.schemas import CriterionResult, EligibilityResult, EligibilityStatus, Status
from extraction.llm_client import LLMClient, get_llm_client


# Explanation generation prompt
EXPLANATION_SYSTEM_PROMPT = """You are an expert at explaining eligibility decisions for college placement drives.

Your task is to generate clear, concise explanations of why a student is or is not eligible for a placement drive.

Guidelines:
1. Start with a clear verdict (Eligible/Not Eligible/Unclear)
2. Cite specific criteria that were checked
3. For FAIL status: clearly state which requirement was not met
4. For PASS status: confirm the student meets the requirement
5. For UNKNOWN status: explain what information is missing
6. Use friendly, professional tone suitable for students
7. Keep explanations concise (3-5 sentences)
8. Include the actual values being compared when relevant

Format:
- Lead with the verdict
- List key criteria (pass/fail/unknown)
- End with actionable next steps if applicable

Example structure:
"You are [eligible/not eligible] for the TechCorp placement drive.

Requirements checked:
- CGPA: Your CGPA of 7.8 meets the minimum requirement of 7.5 ✓
- Branch: CSE is in the allowed list (CSE, ISE) ✓
- Backlogs: You have 0 backlogs, meeting the requirement ✓

You may proceed with registration."

IMPORTANT:
- Base your explanation ONLY on the provided evidence
- Do NOT invent or assume information not in the evidence
- If a criterion status is UNKNOWN, say so clearly
- Cite actual values from student profile and requirements
"""


EXPLANATION_USER_PROMPT_TEMPLATE = """Generate an eligibility explanation for this student and drive:

STUDENT: {student_id}
DRIVE: {drive_id}
OVERALL STATUS: {status}

CRITERION RESULTS:
{criterion_details}

Generate a clear, student-friendly explanation based on these results.
"""


class ExplanationGenerator:
    """Generates natural language explanations from eligibility results."""
    
    def __init__(self, llm_client: LLMClient | None = None):
        """Initialize explanation generator.
        
        Args:
            llm_client: Optional LLM client (creates new if not provided)
        """
        self.llm_client = llm_client or get_llm_client()
    
    def generate(self, result: EligibilityResult) -> str:
        """Generate explanation from eligibility result.
        
        Args:
            result: EligibilityResult with decision and evidence
        
        Returns:
            Natural language explanation string
        """
        # Format criterion details for prompt
        criterion_details = self._format_criterion_results(result.criterion_results)
        
        # Build prompt
        user_prompt = EXPLANATION_USER_PROMPT_TEMPLATE.format(
            student_id=result.student_id,
            drive_id=result.drive_id,
            status=result.status.value,
            criterion_details=criterion_details,
        )
        
        # Generate explanation
        full_prompt = f"{EXPLANATION_SYSTEM_PROMPT}\n\n{user_prompt}"
        
        explanation = self.llm_client.generate(
            prompt=full_prompt,
            temperature=0.3,  # Slightly higher for natural language
        )
        
        return explanation.strip()
    
    def _format_criterion_results(self, results: list[CriterionResult]) -> str:
        """Format criterion results for prompt.
        
        Args:
            results: List of CriterionResult objects
        
        Returns:
            Formatted string with criterion details
        """
        if not results:
            return "No criteria were evaluated."
        
        lines = []
        for i, result in enumerate(results, 1):
            status_symbol = {
                Status.PASS: "✓ PASS",
                Status.FAIL: "✗ FAIL",
                Status.UNKNOWN: "? UNKNOWN",
            }.get(result.status, "UNKNOWN")
            
            criterion_type = result.criterion.criterion_type.replace("_", " ").title()
            
            line = f"{i}. {criterion_type}: {status_symbol}"
            
            if result.student_value is not None:
                line += f"\n   Student value: {result.student_value}"
            
            line += f"\n   Requirement: {result.criterion.operator} {result.criterion.value}"
            
            if result.criterion.scope != "ALL":
                line += f" (scope: {result.criterion.scope})"
            
            if result.message:
                line += f"\n   Note: {result.message}"
            
            lines.append(line)
        
        return "\n\n".join(lines)
    
    def generate_summary(self, result: EligibilityResult) -> str:
        """Generate a brief summary (1-2 sentences).
        
        Args:
            result: EligibilityResult
        
        Returns:
            Brief summary string
        """
        if result.status == EligibilityStatus.ELIGIBLE:
            return f"Student {result.student_id} is eligible for drive {result.drive_id}. All criteria met."
        
        elif result.status == EligibilityStatus.INELIGIBLE:
            # Find failing criteria
            failed = [r for r in result.criterion_results if r.status == Status.FAIL]
            if failed:
                failed_names = [r.criterion.criterion_type for r in failed[:2]]
                reason = ", ".join(failed_names)
                return f"Student {result.student_id} is not eligible for drive {result.drive_id}. Failed: {reason}."
            return f"Student {result.student_id} is not eligible for drive {result.drive_id}."
        
        else:  # UNKNOWN
            return f"Eligibility for student {result.student_id} in drive {result.drive_id} cannot be determined. Missing information."
    
    def generate_with_citations(self, result: EligibilityResult) -> dict[str, Any]:
        """Generate explanation with source citations.
        
        Args:
            result: EligibilityResult
        
        Returns:
            Dict with explanation, summary, citations, and metadata
        """
        explanation = self.generate(result)
        summary = self.generate_summary(result)
        
        # Extract citations from criterion results
        citations = self._extract_citations(result.criterion_results)
        
        return {
            "explanation": explanation,
            "summary": summary,
            "status": result.status.value,
            "student_id": result.student_id,
            "drive_id": result.drive_id,
            "citations": citations,
            "criteria_checked": len(result.criterion_results),
            "criteria_passed": sum(
                1 for r in result.criterion_results if r.status == Status.PASS
            ),
            "criteria_failed": sum(
                1 for r in result.criterion_results if r.status == Status.FAIL
            ),
            "criteria_unknown": sum(
                1 for r in result.criterion_results if r.status == Status.UNKNOWN
            ),
        }
    
    def _extract_citations(self, results: list[CriterionResult]) -> list[dict[str, str]]:
        """Extract source citations from criterion results.
        
        Args:
            results: List of CriterionResult objects
        
        Returns:
            List of citation dicts with criterion_type and source info
        """
        citations = []
        
        for result in results:
            citation = {
                "criterion_type": result.criterion.criterion_type,
                "scope": result.criterion.scope,
            }
            
            # Note: In full implementation, we'd link back to the Fact
            # that provided this criterion via the reconciliation engine
            # For now, we just document the criterion itself
            
            citations.append(citation)
        
        return citations


def generate_explanation(
    result: EligibilityResult,
    llm_client: LLMClient | None = None,
) -> str:
    """Convenience function to generate explanation.
    
    Args:
        result: EligibilityResult to explain
        llm_client: Optional LLM client
    
    Returns:
        Natural language explanation
    """
    generator = ExplanationGenerator(llm_client)
    return generator.generate(result)


def generate_explanation_with_citations(
    result: EligibilityResult,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """Convenience function to generate explanation with citations.
    
    Args:
        result: EligibilityResult to explain
        llm_client: Optional LLM client
    
    Returns:
        Dict with explanation, citations, and metadata
    """
    generator = ExplanationGenerator(llm_client)
    return generator.generate_with_citations(result)
