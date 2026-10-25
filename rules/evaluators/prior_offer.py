from __future__ import annotations

from core.schemas import Criterion, CriterionResult, Status, Student
from rules.evaluators.registry import register


@register("no_prior_offer")
def evaluate_no_prior_offer(criterion: Criterion, student: Student) -> CriterionResult:
    if student.has_prior_offer is None:
        return CriterionResult(
            criterion=criterion,
            status=Status.UNKNOWN,
            student_value=None,
            message="Whether the student has an existing offer is not on record.",
        )

    passed = student.has_prior_offer is False
    return CriterionResult(
        criterion=criterion,
        status=Status.PASS if passed else Status.FAIL,
        student_value=student.has_prior_offer,
        message=(
            "Student has no existing offer."
            if passed
            else "Student already has an existing offer."
        ),
    )
