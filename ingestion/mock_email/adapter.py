"""Mock email adapter for PlaceGuard ingestion pipeline.

Implements the SourceAdapter interface for email-based placement notices.
Uses JSON file storage to simulate email inbox without requiring email infrastructure.
"""

from __future__ import annotations

from datetime import datetime

from core.schemas import RawMessage, SenderRole, SourceType
from ingestion.adapters.base import SourceAdapter
from ingestion.mock_email.store import EmailStore


class MockEmailAdapter(SourceAdapter):
    """Email source adapter using JSON file storage for testing.
    
    Simulates email-based placement notices. In production, this would be replaced
    with a real email adapter (Gmail API, IMAP, etc.).
    """
    
    def __init__(self, store_path: str | None = None):
        """Initialize mock email adapter.
        
        Args:
            store_path: Optional path to JSON store file
        """
        self.store = EmailStore(store_path) if store_path else EmailStore()
    
    def fetch(self) -> list[RawMessage]:
        """Fetch all emails from store and convert to RawMessage format.
        
        Returns:
            List of RawMessage objects
        """
        emails = self.store.load_emails()
        raw_messages = []
        
        for email in emails:
            try:
                raw_message = self._email_to_raw_message(email)
                raw_messages.append(raw_message)
            except (KeyError, ValueError) as e:
                # Skip malformed emails
                print(f"Warning: Skipping malformed email {email.get('message_id')}: {e}")
                continue
        
        return raw_messages
    
    def _email_to_raw_message(self, email: dict) -> RawMessage:
        """Convert email dict to RawMessage.
        
        Args:
            email: Email dict with keys: message_id, from, subject, body, timestamp
        
        Returns:
            RawMessage object
        """
        # Extract sender role from email address
        sender_email = email["from"].lower()
        sender_role = self._infer_sender_role(sender_email)
        
        # Determine source type based on sender
        source_type = self._infer_source_type(sender_email, sender_role)
        
        # Parse timestamp
        if isinstance(email["timestamp"], str):
            timestamp = datetime.fromisoformat(
                email["timestamp"].replace("Z", "+00:00")
            )
        else:
            timestamp = email["timestamp"]
        
        # Combine subject and body for full message text
        body = f"Subject: {email['subject']}\n\n{email['body']}"
        
        return RawMessage(
            message_id=email["message_id"],
            source_type=source_type,
            sender_id=email["from"],
            sender_role=sender_role,
            timestamp=timestamp,
            body=body,
            message_type="email",
            is_forwarded=email.get("is_forwarded", False),
        )
    
    def _infer_sender_role(self, email: str) -> SenderRole:
        """Infer sender role from email address.
        
        Args:
            email: Email address
        
        Returns:
            SenderRole enum value
        """
        email_lower = email.lower()
        
        # Check for placement cell indicators
        if any(keyword in email_lower for keyword in ["placement", "tpo", "training"]):
            return SenderRole.PLACEMENT_CELL
        
        # Check for coordinator indicators
        if any(keyword in email_lower for keyword in ["coordinator", "hod", "dept"]):
            return SenderRole.COORDINATOR
        
        # Default to student
        return SenderRole.STUDENT
    
    def _infer_source_type(self, email: str, sender_role: SenderRole) -> SourceType:
        """Infer source type from email and sender role.
        
        Args:
            email: Email address
            sender_role: Detected sender role
        
        Returns:
            SourceType enum value
        """
        # Map sender role to source type for email channel
        if sender_role == SenderRole.PLACEMENT_CELL:
            return SourceType.PLACEMENT_CELL_EMAIL
        elif sender_role == SenderRole.COORDINATOR:
            return SourceType.COORDINATOR_WHATSAPP  # Using WhatsApp type for coordinators
        else:
            return SourceType.STUDENT_WHATSAPP  # Using WhatsApp type for students
    
    def send_email(self, email: dict) -> None:
        """Add a new email to the store (for testing).
        
        Args:
            email: Email dict to add
        """
        self.store.add_email(email)
