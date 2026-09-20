"""Ports for hybrid message search. Azure adapters implement these protocols."""

from dataclasses import dataclass
from typing import Protocol

from app.models import Message, MessageSource


@dataclass(frozen=True)
class SearchDocument:
    """Projection of a canonical message indexed for retrieval."""

    key: str
    source: MessageSource
    message_id: str
    conversation_id: str
    subject: str | None
    sender: str
    recipients: tuple[str, ...]
    participants: tuple[str, ...]
    text: str
    timestamp: str
    content_hash: str
    embedding: list[float]


@dataclass(frozen=True)
class SearchHit:
    """A single retrieval result with its hybrid relevance score."""

    message: Message
    score: float


class EmbeddingPort(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class SearchIndexPort(Protocol):
    async def ensure_index(self) -> None: ...

    async def upload_documents(self, documents: list[SearchDocument]) -> None: ...

    async def hybrid_search(
        self, query: str, query_vector: list[float], *, top: int = 10
    ) -> list[SearchHit]: ...
