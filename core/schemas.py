"""Shared Pydantic contracts used across ingestion, rules, and (later) extraction/reconciliation.

See DESIGN.md sections 3 and 6. Every stage of the pipeline reads/writes these types rather than
ad-hoc dicts, so new criteria, sources, or evaluators are additive instead of requiring edits here.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class SenderRole(str, Enum):
    PLACEMENT_CELL = "placement_cell"
    COORDINATOR = "coordinator"
    STUDENT = "student"


class SourceType(str, Enum):
    """Maps to the authority ranking in DESIGN.md 3.1. Lower rank number = higher authority."""

    OFFICIAL_COMPANY_PDF = "official_company_pdf"
    PLACEMENT_CELL_WHATSAPP = "placement_cell_whatsapp"
    PLACEMENT_CELL_EMAIL = "placement_cell_email"
    COORDINATOR_WHATSAPP = "coordinator_whatsapp"
    STUDENT_PORTAL = "student_portal"
    STUDENT_WHATSAPP = "student_whatsapp"


SOURCE_AUTHORITY_RANK: dict[SourceType, int] = {
    SourceType.OFFICIAL_COMPANY_PDF: 1,
    SourceType.PLACEMENT_CELL_WHATSAPP: 2,
    SourceType.PLACEMENT_CELL_EMAIL: 2,
    SourceType.COORDINATOR_WHATSAPP: 3,
    SourceType.STUDENT_PORTAL: 4,
    SourceType.STUDENT_WHATSAPP: 5,
}


class RawMessage(BaseModel):
    """Normalized shape every SourceAdapter.fetch() must return, regardless of channel."""

    message_id: str
    source_type: SourceType
    sender_id: str
    sender_role: SenderRole
    timestamp: datetime
    body: str
    message_type: str = "text"
    is_forwarded: bool = False


class Student(BaseModel):
    student_id: str
    name: str
    cgpa: float | None = None
    branch: str | None = None
    backlogs: int | None = None
    has_prior_offer: bool | None = None
    tenth_pct: float | None = None
    twelfth_pct: float | None = None


class Criterion(BaseModel):
    """One structured, extracted eligibility requirement.

    (drive_id, criterion_type, scope) is the rule-key from DESIGN.md 3.3 — two criteria with the
    same key are considered the same rule for reconciliation purposes.
    """

    drive_id: str
    criterion_type: str
    operator: str  # "gte" | "lte" | "eq" | "in" | "not_in"
    value: Any
    scope: str = "ALL"


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    UNKNOWN = "UNKNOWN"


class CriterionResult(BaseModel):
    criterion: Criterion
    status: Status
    student_value: Any = None
    message: str


class EligibilityResult(BaseModel):
    student_id: str
    drive_id: str
    status: EligibilityStatus
    criterion_results: list[CriterionResult]
