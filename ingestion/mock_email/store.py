"""Simple JSON file-based email storage for mock email adapter.

Provides read/write operations for simulated email messages.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class EmailStore:
    """Simple JSON-based email message storage."""
    
    def __init__(self, store_path: str | Path = "ingestion/mock_email/emails.json"):
        """Initialize email store.
        
        Args:
            store_path: Path to JSON file storing emails
        """
        self.store_path = Path(store_path)
        self._ensure_store_exists()
    
    def _ensure_store_exists(self) -> None:
        """Create empty store file if it doesn't exist."""
        if not self.store_path.exists():
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            self.store_path.write_text("[]", encoding="utf-8")
    
    def load_emails(self) -> list[dict[str, Any]]:
        """Load all emails from store.
        
        Returns:
            List of email message dicts
        """
        try:
            content = self.store_path.read_text(encoding="utf-8")
            emails = json.loads(content)
            
            # Convert timestamp strings to datetime objects
            for email in emails:
                if isinstance(email.get("timestamp"), str):
                    email["timestamp"] = datetime.fromisoformat(
                        email["timestamp"].replace("Z", "+00:00")
                    )
            
            return emails
        except (json.JSONDecodeError, FileNotFoundError) as e:
            raise ValueError(f"Failed to load emails from {self.store_path}: {e}")
    
    def save_emails(self, emails: list[dict[str, Any]]) -> None:
        """Save emails to store.
        
        Args:
            emails: List of email message dicts
        """
        # Convert datetime objects to ISO strings
        serializable_emails = []
        for email in emails:
            email_copy = email.copy()
            if isinstance(email_copy.get("timestamp"), datetime):
                email_copy["timestamp"] = email_copy["timestamp"].isoformat()
            serializable_emails.append(email_copy)
        
        self.store_path.write_text(
            json.dumps(serializable_emails, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    
    def add_email(self, email: dict[str, Any]) -> None:
        """Add a single email to store.
        
        Args:
            email: Email message dict
        """
        emails = self.load_emails()
        emails.append(email)
        self.save_emails(emails)
    
    def get_email_by_id(self, message_id: str) -> dict[str, Any] | None:
        """Retrieve a specific email by message ID.
        
        Args:
            message_id: Email message ID
            
        Returns:
            Email dict or None if not found
        """
        emails = self.load_emails()
        for email in emails:
            if email.get("message_id") == message_id:
                return email
        return None
    
    def clear_store(self) -> None:
        """Clear all emails from store."""
        self.save_emails([])
