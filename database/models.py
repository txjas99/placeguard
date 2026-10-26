"""SQLAlchemy ORM models for PlaceGuard database.

Key design principles from DESIGN.md:
1. Facts table is immutable and append-only (event-sourced)
2. No UPDATE/DELETE on facts - only INSERT and SELECT
3. Current state is derived via reconciliation queries, not stored directly
4. Full provenance tracking on every fact
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Student(Base):
    """Student profile with eligibility-relevant attributes."""
    
    __tablename__ = "students"
    
    student_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    
    # Eligibility criteria fields (nullable to support UNKNOWN state)
    cgpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    branch: Mapped[str | None] = mapped_column(String(50), nullable=True)
    backlogs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_prior_offer: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tenth_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    twelfth_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    def __repr__(self) -> str:
        return f"<Student {self.student_id} ({self.name})>"


class Drive(Base):
    """Placement drive/company metadata."""
    
    __tablename__ = "drives"
    
    drive_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active | closed | cancelled
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    def __repr__(self) -> str:
        return f"<Drive {self.drive_id} ({self.company_name})>"


class Fact(Base):
    """Immutable, append-only event log of extracted eligibility criteria.
    
    CRITICAL: This table is write-once. Never UPDATE or DELETE.
    
    Each fact represents one extracted criterion from one source at one point in time.
    The reconciliation engine queries this table to derive the "current" state by
    applying authority ranking and temporal logic (DESIGN.md 3.1).
    """
    
    __tablename__ = "facts"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Provenance: where did this fact come from?
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    authority_rank: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # Temporal: when was this fact asserted?
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )  # When the source communicated this
    effective_timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )  # When this fact takes effect (may differ for scheduled updates)
    
    # Rule key: (drive_id, criterion_type, scope) from DESIGN.md 3.3
    drive_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    criterion_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(
        String(50), nullable=False, default="ALL", index=True
    )
    
    # Criterion value
    operator: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # gte | lte | eq | in | not_in
    value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-serialized value
    
    # Supersession tracking (DESIGN.md 3.2)
    is_correction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supersedes_ref: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # source_id of fact this supersedes
    
    # Audit trail
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )  # When LLM extraction occurred
    raw_notice_text: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Original notice for audit
    
    def __repr__(self) -> str:
        return (
            f"<Fact {self.drive_id}.{self.criterion_type}={self.value} "
            f"from {self.source_type} at {self.timestamp}>"
        )


class ExtractedCriterion(Base):
    """Derived view of current criteria per drive after reconciliation.
    
    This table is populated/updated by the reconciliation engine after processing
    facts. It represents the "current truth" after applying authority ranking,
    temporal logic, and supersession detection.
    
    This is NOT append-only like Facts — it's a materialized view that gets
    updated when reconciliation runs.
    """
    
    __tablename__ = "extracted_criteria"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Rule key
    drive_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    criterion_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(50), nullable=False, default="ALL")
    
    # Current value
    operator: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Provenance of current value
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    authority_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Status
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    reconciled_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    def __repr__(self) -> str:
        return (
            f"<ExtractedCriterion {self.drive_id}.{self.criterion_type}={self.value} "
            f"from {self.source_type}>"
        )
