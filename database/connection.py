"""Database connection management with session handling and pooling."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings

# Create engine with connection pooling
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,
    max_overflow=10,
    echo=settings.database_echo,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI routes to get database session.
    
    Usage:
        @app.get("/students")
        def list_students(db: Session = Depends(get_db)):
            return crud.get_students(db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database session in non-FastAPI code.
    
    Usage:
        with get_db_context() as db:
            student = crud.get_student(db, student_id="s1")
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database by creating all tables.
    
    NOTE: In production, use Alembic migrations instead.
    This is useful for testing and development.
    """
    from database.models import Base
    
    Base.metadata.create_all(bind=engine)
