"""Database module for PlaceGuard.

Provides PostgreSQL connection management, ORM models, and CRUD operations for:
- Event-sourced facts (immutable, append-only)
- Student records
- Placement drives
- Extracted criteria (derived views)
"""

from database.connection import get_db, init_db
from database.models import Base, Drive, ExtractedCriterion, Fact, Student

__all__ = [
    "Base",
    "Student",
    "Drive",
    "Fact",
    "ExtractedCriterion",
    "get_db",
    "init_db",
]
