"""In-memory message store for the mock WhatsApp console.

Stands in for whatever durable store the real adapter will read from later (DESIGN.md 9.1:
the console mimics the WhatsApp Business Cloud API webhook shape so swapping this module
for a real integration is an adapter change, not a rewrite).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from core.schemas import RawMessage, SenderRole, SourceType

_SENDER_ROLE_TO_SOURCE_TYPE: dict[SenderRole, SourceType] = {
    SenderRole.PLACEMENT_CELL: SourceType.PLACEMENT_CELL_WHATSAPP,
    SenderRole.COORDINATOR: SourceType.COORDINATOR_WHATSAPP,
    SenderRole.STUDENT: SourceType.STUDENT_WHATSAPP,
}

_messages: list[RawMessage] = []


def add_message(
    sender_id: str,
    sender_role: SenderRole,
    body: str,
    is_forwarded: bool = False,
) -> RawMessage:
    message = RawMessage(
        message_id=str(uuid.uuid4()),
        source_type=_SENDER_ROLE_TO_SOURCE_TYPE[sender_role],
        sender_id=sender_id,
        sender_role=sender_role,
        timestamp=datetime.now(timezone.utc),
        body=body,
        message_type="text",
        is_forwarded=is_forwarded,
    )
    _messages.append(message)
    return message


def get_all() -> list[RawMessage]:
    return list(_messages)


def clear() -> None:
    """Test/demo-reset helper only — never called from production code paths."""
    _messages.clear()
