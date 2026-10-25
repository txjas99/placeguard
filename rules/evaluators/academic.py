"""Evaluators for numeric academic-threshold criteria: min_cgpa, min_10th_pct, min_12th_pct."""

from __future__ import annotations

from core.schemas import Criterion, CriterionResult, Status, Student
from rules.evaluators.registry import register


def _evaluate_min_threshold(
    criterion: Criterion, student_value: float | None, field_label: str
) -> CriterionResult:
    if student_value is None:
        return CriterionResult(
            criterion=criterion,
            status=Status.UNKNOWN,
            student_value=None,
            message=f"{field_label} is not on record for this student.",
        )

    threshold = criterion.value
    passed = student_value >= threshold
    return CriterionResult(
        criterion=criterion,
        status=Status.PASS if passed else Status.FAIL,
        student_value=student_value,
        message=(
            f"{field_label} {student_value} "
            f"{'meets' if passed else 'does not meet'} minimum {threshold}."
        ),
    )


@register("min_cgpa")
def evaluate_min_cgpa(criterion: Criterion, student: Student) -> CriterionResult:
    return _evaluate_min_threshold(criterion, student.cgpa, "CGPA")


@register("min_10th_pct")
def evaluate_min_10th_pct(criterion: Criterion, student: Student) -> CriterionResult:
    return _evaluate_min_threshold(criterion, student.tenth_pct, "10th percentage")


@register("min_12th_pct")
def evaluate_min_12th_pct(criterion: Criterion, student: Student) -> CriterionResult:
    return _evaluate_min_threshold(criterion, student.twelfth_pct, "12th percentage")
