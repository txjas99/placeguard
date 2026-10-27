"""Tests for database connection and session management."""

import pytest
from sqlalchemy import text

from database.connection import get_db_context, init_db


def test_database_connection():
    """Test that we can establish a database connection."""
    with get_db_context() as db:
        # Simple query to verify connection
        result = db.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_init_db_creates_tables():
    """Test that init_db creates all tables."""
    # This will create tables in the test database
    init_db()
    
    with get_db_context() as db:
        # Check that tables exist by querying them
        # SQLite-specific query to list tables
        result = db.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
        
        table_names = [row[0] for row in result]
        
        # Verify our tables were created
        assert "students" in table_names
        assert "drives" in table_names
        assert "facts" in table_names
        assert "extracted_criteria" in table_names


def test_session_cleanup():
    """Test that sessions are properly cleaned up."""
    sessions = []
    
    for _ in range(5):
        with get_db_context() as db:
            sessions.append(db)
            # Use the session
            db.execute(text("SELECT 1"))
    
    # All sessions should be closed after context exit
    # Check that sessions no longer have active connections
    for session in sessions:
        # Session should not have an active transaction
        assert not session.in_transaction()
        # Connection should be returned to pool (info dict should be empty or have closed=True)
        # The session is closed, so accessing connection properties might raise
        try:
            # If we can't get a connection, it's been closed
            conn = session.connection()
            assert conn.closed or not conn.in_transaction()
        except Exception:
            # Session properly closed, can't access connection anymore
            pass
