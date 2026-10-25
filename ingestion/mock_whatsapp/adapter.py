from __future__ import annotations

from core.schemas import RawMessage
from ingestion.adapters.base import SourceAdapter
from ingestion.mock_whatsapp import store


class MockWhatsAppAdapter(SourceAdapter):
    """Reads whatever has been posted through the mock console (DESIGN.md 9.1 / 6 build order).

    A real adapter (WhatsApp Business Cloud API) would fetch from a webhook-fed queue or
    database instead of this in-memory store, but returns the same RawMessage shape, so
    nothing downstream of ingestion needs to change when this is swapped in later.
    """

    def fetch(self) -> list[RawMessage]:
        return store.get_all()
