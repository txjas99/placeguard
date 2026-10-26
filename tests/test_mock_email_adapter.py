"""Unit tests for mock email adapter.

Tests the email source adapter and JSON store functionality.
"""

from datetime import datetime
from pathlib import Path
import tempfile
import json

import pytest

from core.schemas import RawMessage, SenderRole, SourceType
from ingestion.mock_email.adapter import MockEmailAdapter
from ingestion.mock_email.store import EmailStore


class TestEmailStore:
    """Test email store functionality."""
    
    def test_create_empty_store(self):
        """Test creating an empty store file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_emails.json"
            store = EmailStore(store_path)
            
            assert store_path.exists()
            emails = store.load_emails()
            assert emails == []
    
    def test_save_and_load_emails(self):
        """Test saving and loading emails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_emails.json"
            store = EmailStore(store_path)
            
            test_emails = [
                {
                    "message_id": "email_001",
                    "from": "placement@college.edu",
                    "subject": "Test Subject",
                    "body": "Test Body",
                    "timestamp": datetime(2026, 10, 26, 10, 0, 0),
                    "is_forwarded": False,
                }
            ]
            
            store.save_emails(test_emails)
            loaded = store.load_emails()
            
            assert len(loaded) == 1
            assert loaded[0]["message_id"] == "email_001"
            assert isinstance(loaded[0]["timestamp"], datetime)
    
    def test_add_email(self):
        """Test adding a single email."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_emails.json"
            store = EmailStore(store_path)
            
            email = {
                "message_id": "email_001",
                "from": "test@college.edu",
                "subject": "Test",
                "body": "Body",
                "timestamp": datetime(2026, 10, 26, 10, 0, 0),
            }
            
            store.add_email(email)
            loaded = store.load_emails()
            
            assert len(loaded) == 1
            assert loaded[0]["message_id"] == "email_001"
    
    def test_get_email_by_id(self):
        """Test retrieving specific email by ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_emails.json"
            store = EmailStore(store_path)
            
            emails = [
                {
                    "message_id": "email_001",
                    "from": "test1@college.edu",
                    "subject": "Test 1",
                    "body": "Body 1",
                    "timestamp": datetime(2026, 10, 26, 10, 0, 0),
                },
                {
                    "message_id": "email_002",
                    "from": "test2@college.edu",
                    "subject": "Test 2",
                    "body": "Body 2",
                    "timestamp": datetime(2026, 10, 26, 11, 0, 0),
                },
            ]
            
            store.save_emails(emails)
            
            email = store.get_email_by_id("email_002")
            assert email is not None
            assert email["subject"] == "Test 2"
            
            missing = store.get_email_by_id("email_999")
            assert missing is None
    
    def test_clear_store(self):
        """Test clearing all emails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_emails.json"
            store = EmailStore(store_path)
            
            store.add_email({
                "message_id": "email_001",
                "from": "test@college.edu",
                "subject": "Test",
                "body": "Body",
                "timestamp": datetime(2026, 10, 26, 10, 0, 0),
            })
            
            assert len(store.load_emails()) == 1
            
            store.clear_store()
            assert len(store.load_emails()) == 0


class TestMockEmailAdapter:
    """Test mock email adapter functionality."""
    
    def test_fetch_emails(self):
        """Test fetching emails from store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_emails.json"
            
            # Create test emails
            emails = [
                {
                    "message_id": "email_001",
                    "from": "placement@college.edu",
                    "subject": "Test Notice",
                    "body": "Eligibility criteria",
                    "timestamp": "2026-10-26T10:00:00",
                    "is_forwarded": False,
                }
            ]
            
            store_path.write_text(json.dumps(emails))
            
            adapter = MockEmailAdapter(str(store_path))
            messages = adapter.fetch()
            
            assert len(messages) == 1
            assert isinstance(messages[0], RawMessage)
            assert messages[0].message_id == "email_001"
            assert messages[0].message_type == "email"
    
    def test_infer_sender_role_placement_cell(self):
        """Test sender role inference for placement cell."""
        adapter = MockEmailAdapter()
        
        assert adapter._infer_sender_role("placement@college.edu") == SenderRole.PLACEMENT_CELL
        assert adapter._infer_sender_role("tpo@college.edu") == SenderRole.PLACEMENT_CELL
        assert adapter._infer_sender_role("training@college.edu") == SenderRole.PLACEMENT_CELL
    
    def test_infer_sender_role_coordinator(self):
        """Test sender role inference for coordinator."""
        adapter = MockEmailAdapter()
        
        assert adapter._infer_sender_role("coordinator@college.edu") == SenderRole.COORDINATOR
        assert adapter._infer_sender_role("hod.cse@college.edu") == SenderRole.COORDINATOR
        assert adapter._infer_sender_role("dept.head@college.edu") == SenderRole.COORDINATOR
    
    def test_infer_sender_role_student(self):
        """Test sender role inference for student."""
        adapter = MockEmailAdapter()
        
        assert adapter._infer_sender_role("student123@college.edu") == SenderRole.STUDENT
        assert adapter._infer_sender_role("john.doe@college.edu") == SenderRole.STUDENT
    
    def test_infer_source_type_placement_cell(self):
        """Test source type inference for placement cell."""
        adapter = MockEmailAdapter()
        
        source_type = adapter._infer_source_type(
            "placement@college.edu",
            SenderRole.PLACEMENT_CELL
        )
        
        assert source_type == SourceType.PLACEMENT_CELL_EMAIL
    
    def test_email_to_raw_message_combines_subject_body(self):
        """Test that subject and body are combined in raw message."""
        adapter = MockEmailAdapter()
        
        email = {
            "message_id": "email_001",
            "from": "placement@college.edu",
            "subject": "Important Notice",
            "body": "Detailed information here",
            "timestamp": datetime(2026, 10, 26, 10, 0, 0),
            "is_forwarded": False,
        }
        
        message = adapter._email_to_raw_message(email)
        
        assert "Subject: Important Notice" in message.body
        assert "Detailed information here" in message.body
    
    def test_fetch_skips_malformed_emails(self):
        """Test that malformed emails are skipped with warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_emails.json"
            
            # Create mix of valid and invalid emails
            emails = [
                {
                    "message_id": "email_001",
                    "from": "placement@college.edu",
                    "subject": "Valid",
                    "body": "Valid body",
                    "timestamp": "2026-10-26T10:00:00",
                },
                {
                    "message_id": "email_002",
                    # Missing required fields
                    "subject": "Invalid",
                },
                {
                    "message_id": "email_003",
                    "from": "placement@college.edu",
                    "subject": "Also Valid",
                    "body": "Valid body",
                    "timestamp": "2026-10-26T12:00:00",
                },
            ]
            
            store_path.write_text(json.dumps(emails))
            
            adapter = MockEmailAdapter(str(store_path))
            messages = adapter.fetch()
            
            # Should only get 2 valid messages
            assert len(messages) == 2
            assert messages[0].message_id == "email_001"
            assert messages[1].message_id == "email_003"
    
    def test_send_email_adds_to_store(self):
        """Test that send_email adds email to store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_emails.json"
            adapter = MockEmailAdapter(str(store_path))
            
            email = {
                "message_id": "email_new",
                "from": "placement@college.edu",
                "subject": "New Email",
                "body": "New body",
                "timestamp": datetime(2026, 10, 26, 15, 0, 0),
            }
            
            adapter.send_email(email)
            
            # Verify it was added
            messages = adapter.fetch()
            assert len(messages) == 1
            assert messages[0].message_id == "email_new"


class TestEmailAdapterIntegration:
    """Integration tests with sample data."""
    
    def test_load_sample_emails(self):
        """Test loading from actual sample emails.json."""
        # Use the actual sample emails file
        adapter = MockEmailAdapter("ingestion/mock_email/emails.json")
        messages = adapter.fetch()
        
        # Should have 5 sample emails
        assert len(messages) == 5
        
        # Check first email
        assert messages[0].message_id == "email_001"
        assert messages[0].source_type == SourceType.PLACEMENT_CELL_EMAIL
        assert messages[0].sender_role == SenderRole.PLACEMENT_CELL
        
        # Check student forward (should be detected as forwarded)
        student_msg = next(m for m in messages if m.message_id == "email_004")
        assert student_msg.is_forwarded is True
        assert student_msg.sender_role == SenderRole.STUDENT
