from __future__ import annotations

from core.schemas import Criterion, CriterionResult, Status, Student
from rules.evaluators.registry import register


@register("branch")
def evaluate_branch(criterion: Criterion, student: Student) -> CriterionResult:
    if student.branch is None:
        return CriterionResult(
            criterion=criterion,
            status=Status.UNKNOWN,
            student_value=None,
            message="Student branch is not on record.",
        )

    allowed_branches: list[str] = criterion.value
    passed = student.branch in allowed_branches
    return CriterionResult(
        criterion=criterion,
        status=Status.PASS if passed else Status.FAIL,
        student_value=student.branch,
        message=(
            f"Branch {student.branch} is "
            f"{'' if passed else 'not '}one of the allowed branches {allowed_branches}."
        ),
    )
