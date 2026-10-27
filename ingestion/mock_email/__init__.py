"""Mock email ingestion adapter for testing and development.

Simulates email-based placement notices without requiring actual email infrastructure.
"""

from ingestion.mock_email.adapter import MockEmailAdapter

__all__ = ["MockEmailAdapter"]
