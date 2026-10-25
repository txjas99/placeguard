"""SourceAdapter interface (DESIGN.md 2.1).

Every ingestion channel — mock or real — implements this same contract and returns
RawMessage objects in the same normalized shape. Adding a new channel later (real
WhatsApp Business API, Gmail, SMS, ...) means writing one new adapter class; nothing
downstream of ingestion changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.schemas import RawMessage


class SourceAdapter(ABC):
    @abstractmethod
    def fetch(self) -> list[RawMessage]:
        """Return all messages currently available from this source, normalized to RawMessage."""
        raise NotImplementedError
