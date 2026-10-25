from core.schemas import Criterion, EligibilityStatus, Status, Student
from rules.eligibility_engine import evaluate_eligibility

DRIVE_ID = "drive_104"


def _criteria() -> list[Criterion]:
    return [
        Criterion(drive_id=DRIVE_ID, criterion_type="min_cgpa", operator="gte", value=7.5),
        Criterion(drive_id=DRIVE_ID, criterion_type="branch", operator="in", value=["CSE", "ISE"]),
        Criterion(drive_id=DRIVE_ID, criterion_type="max_backlogs", operator="lte", value=0),
        Criterion(drive_id=DRIVE_ID, criterion_type="no_prior_offer", operator="eq", value=True),
    ]


def test_all_pass_is_eligible():
    student = Student(
        student_id="s1", name="A", cgpa=8.1, branch="CSE", backlogs=0, has_prior_offer=False
    )
    result = evaluate_eligibility(student, _criteria())
    assert result.status == EligibilityStatus.ELIGIBLE
    assert all(r.status == Status.PASS for r in result.criterion_results)


def test_single_failure_is_ineligible():
    student = Student(
        student_id="s2", name="B", cgpa=7.2, branch="CSE", backlogs=0, has_prior_offer=False
    )
    result = evaluate_eligibility(student, _criteria())
    assert result.status == EligibilityStatus.INELIGIBLE


def test_missing_data_with_no_failure_is_unknown():
    student = Student(
        student_id="s3", name="C", cgpa=8.1, branch="CSE", backlogs=None, has_prior_offer=False
    )
    result = evaluate_eligibility(student, _criteria())
    assert result.status == EligibilityStatus.UNKNOWN


def test_failure_takes_priority_over_unknown():
    """A confirmed FAIL must win even when another criterion is also UNKNOWN (DESIGN.md 3.4)."""
    student = Student(
        student_id="s4", name="D", cgpa=7.0, branch="CSE", backlogs=None, has_prior_offer=False
    )
    result = evaluate_eligibility(student, _criteria())
    assert result.status == EligibilityStatus.INELIGIBLE


def test_all_criteria_are_evaluated_without_short_circuiting():
    student = Student(
        student_id="s5", name="E", cgpa=7.0, branch="ECE", backlogs=2, has_prior_offer=True
    )
    result = evaluate_eligibility(student, _criteria())
    assert len(result.criterion_results) == 4
    assert all(r.status == Status.FAIL for r in result.criterion_results)
    assert result.status == EligibilityStatus.INELIGIBLE


def test_branch_not_allowed_fails():
    student = Student(
        student_id="s6", name="F", cgpa=9.0, branch="MECH", backlogs=0, has_prior_offer=False
    )
    result = evaluate_eligibility(student, _criteria())
    assert result.status == EligibilityStatus.INELIGIBLE
    branch_result = next(r for r in result.criterion_results if r.criterion.criterion_type == "branch")
    assert branch_result.status == Status.FAIL
