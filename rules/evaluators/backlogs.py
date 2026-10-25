from __future__ import annotations

from core.schemas import Criterion, CriterionResult, Status, Student
from rules.evaluators.registry import register


@register("max_backlogs")
def evaluate_max_backlogs(criterion: Criterion, student: Student) -> CriterionResult:
    if student.backlogs is None:
        return CriterionResult(
            criterion=criterion,
            status=Status.UNKNOWN,
            student_value=None,
            message="Student backlog count is not on record.",
        )

    max_allowed = criterion.value
    passed = student.backlogs <= max_allowed
    return CriterionResult(
        criterion=criterion,
        status=Status.PASS if passed else Status.FAIL,
        student_value=student.backlogs,
        message=(
            f"Backlog count {student.backlogs} "
            f"{'is within' if passed else 'exceeds'} the allowed maximum of {max_allowed}."
        ),
    )
