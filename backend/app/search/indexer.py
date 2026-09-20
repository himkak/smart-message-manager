"""Indexes canonical messages into the search index, skipping unchanged content."""

import logging
from datetime import UTC, datetime

from app.models import Message
from app.repositories.protocols import SearchIndexStateRepository
from app.search.content import content_hash, embedding_text
from app.search.protocols import EmbeddingPort, SearchDocument, SearchIndexPort

logger = logging.getLogger(__name__)


class MessageIndexer:
    """Embeds and uploads only messages whose `subject + sender + text` changed."""

    def __init__(
        self,
        *,
        search_index: SearchIndexPort,
        embeddings: EmbeddingPort,
        index_state: SearchIndexStateRepository,
    ) -> None:
        self._search_index = search_index
        self._embeddings = embeddings
        self._index_state = index_state

    async def index_messages(self, messages: list[Message]) -> int:
        """Index the given messages and return how many were newly embedded/uploaded."""
        logger.info("[MessageIndexer] considering %d message(s) for indexing", len(messages))
        pending: list[SearchDocument] = []
        skipped = 0
        for message in messages:
            digest = content_hash(subject=message.subject, sender=message.sender, text=message.text)
            if await self._index_state.get_hash(message.source, message.id) == digest:
                skipped += 1
                continue
            vector = await self._embeddings.embed(
                embedding_text(subject=message.subject, sender=message.sender, text=message.text)
            )
            pending.append(
                SearchDocument(
                    key=f"{message.source.value}_{message.id}",
                    source=message.source,
                    message_id=message.id,
                    conversation_id=message.conversation_id,
                    subject=message.subject,
                    sender=message.sender,
                    recipients=message.recipients,
                    participants=message.participants,
                    text=message.text,
                    timestamp=message.timestamp.isoformat(),
                    content_hash=digest,
                    embedding=vector,
                )
            )

        logger.info(
            "[MessageIndexer] skipped %d unchanged message(s); %d need embedding/upload",
            skipped,
            len(pending),
        )
        if pending:
            await self._search_index.upload_documents(pending)
            indexed_at = datetime.now(UTC)
            for document in pending:
                await self._index_state.set_hash(
                    document.source, document.message_id, document.content_hash, indexed_at=indexed_at
                )
        return len(pending)
