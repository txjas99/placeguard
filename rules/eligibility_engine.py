"""Deterministic eligibility rule engine (DESIGN.md 1, 3.4).

No LLM call happens anywhere in this module. Every criterion is evaluated independently
(no short-circuiting), then aggregated by priority: any FAIL -> INELIGIBLE, else any
UNKNOWN -> UNKNOWN, else ELIGIBLE. A confirmed failure is always conclusive; missing data
is never silently treated as a pass.
"""

from __future__ import annotations

from core.schemas import Criterion, EligibilityResult, EligibilityStatus, Status, Student
from rules.evaluators import get_evaluator


def evaluate_eligibility(student: Student, criteria: list[Criterion]) -> EligibilityResult:
    results = [get_evaluator(criterion.criterion_type)(criterion, student) for criterion in criteria]

    statuses = {result.status for result in results}
    if Status.FAIL in statuses:
        overall = EligibilityStatus.INELIGIBLE
    elif Status.UNKNOWN in statuses:
        overall = EligibilityStatus.UNKNOWN
    else:
        overall = EligibilityStatus.ELIGIBLE

    drive_id = criteria[0].drive_id if criteria else "UNKNOWN_DRIVE"
    return EligibilityResult(
        student_id=student.student_id,
        drive_id=drive_id,
        status=overall,
        criterion_results=results,
    )
