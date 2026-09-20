"""Contracts for source connectors. No connector implementation ships in Phase 0."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SyncResult:
    messages_processed: int
    cursor: str
    indexed: int = 0


class MessageConnector(Protocol):
    async def initial_sync(self) -> SyncResult: ...

    async def incremental_sync(self, cursor: str | None = None) -> SyncResult: ...
