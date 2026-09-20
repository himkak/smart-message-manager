"""Persistence ports. SQL and future Cosmos adapters implement these protocols."""

from datetime import datetime
from typing import Protocol

from app.models import Conversation, Message, MessageSource


class MessageRepository(Protocol):
    async def upsert(self, message: Message) -> Message: ...

    async def get(self, source: MessageSource, message_id: str) -> Message | None: ...

    async def list_for_conversation(
        self, source: MessageSource, conversation_id: str, *, limit: int = 100
    ) -> list[Message]: ...

    async def list_all(self, source: MessageSource, *, limit: int = 1000) -> list[Message]: ...


class ConversationRepository(Protocol):
    async def upsert(self, conversation: Conversation) -> Conversation: ...

    async def get(self, source: MessageSource, conversation_id: str) -> Conversation | None: ...


class SyncStateRepository(Protocol):
    async def get_cursor(self, source: MessageSource) -> str | None: ...

    async def set_cursor(
        self, source: MessageSource, cursor: str, *, updated_at: datetime
    ) -> None: ...


class SearchIndexStateRepository(Protocol):
    """Tracks the last-indexed content hash per message so unchanged content is not re-embedded."""

    async def get_hash(self, source: MessageSource, message_id: str) -> str | None: ...

    async def set_hash(
        self, source: MessageSource, message_id: str, content_hash: str, *, indexed_at: datetime
    ) -> None: ...

