"""Idempotent initial and incremental Gmail synchronization.

Messages are never persisted to SQLite. Each synced message is normalized and
handed directly to the search indexer, which embeds it (via Azure OpenAI) and
uploads it to Azure AI Search -- that index is the only durable store of message
content. `SyncStateRepository` still tracks the Gmail history cursor, since that
is sync bookkeeping, not message content.
"""

from datetime import UTC, datetime
from typing import Protocol

from app.connectors.gmail.client import GmailHistoryExpiredError
from app.connectors.gmail.normalizer import normalize_gmail_message
from app.connectors.protocols import SyncResult
from app.models import Message, MessageSource
from app.repositories.protocols import SyncStateRepository
from app.search.indexer import MessageIndexer


class GmailClient(Protocol):
    async def profile(self) -> dict: ...
    async def list_messages(self, page_token: str | None = None) -> dict: ...
    async def get_message(self, message_id: str) -> dict: ...
    async def list_history(self, start_history_id: str, page_token: str | None = None) -> dict: ...


class GmailConnector:
    def __init__(
        self,
        client: GmailClient,
        indexer: MessageIndexer,
        sync_state: SyncStateRepository,
    ) -> None:
        self._client = client
        self._indexer = indexer
        self._sync_state = sync_state

    async def _fetch_message(self, message_id: str) -> Message:
        return normalize_gmail_message(await self._client.get_message(message_id))

    async def initial_sync(self) -> SyncResult:
        fetched: list[Message] = []
        page_token: str | None = None
        while True:
            page = await self._client.list_messages(page_token)
            for summary in page.get("messages", []):
                fetched.append(await self._fetch_message(summary["id"]))
            page_token = page.get("nextPageToken")
            if not page_token:
                break
        indexed = await self._indexer.index_messages(fetched)
        profile = await self._client.profile()
        cursor = str(profile["historyId"])
        await self._sync_state.set_cursor(MessageSource.GMAIL, cursor, updated_at=datetime.now(UTC))
        return SyncResult(messages_processed=len(fetched), cursor=cursor, indexed=indexed)

    async def incremental_sync(self, cursor: str | None = None) -> SyncResult:
        start_cursor = cursor or await self._sync_state.get_cursor(MessageSource.GMAIL)
        if not start_cursor:
            return await self.initial_sync()
        fetched: list[Message] = []
        seen_message_ids: set[str] = set()
        page_token: str | None = None
        try:
            while True:
                page = await self._client.list_history(start_cursor, page_token)
                for event in page.get("history", []):
                    for added in event.get("messagesAdded", []):
                        message_id = str(added["message"]["id"])
                        if message_id not in seen_message_ids:
                            fetched.append(await self._fetch_message(message_id))
                            seen_message_ids.add(message_id)
                page_token = page.get("nextPageToken")
                if not page_token:
                    break
        except GmailHistoryExpiredError:
            return await self.initial_sync()

        indexed = await self._indexer.index_messages(fetched)
        profile = await self._client.profile()
        latest_cursor = str(profile["historyId"])
        await self._sync_state.set_cursor(MessageSource.GMAIL, latest_cursor, updated_at=datetime.now(UTC))
        return SyncResult(messages_processed=len(fetched), cursor=latest_cursor, indexed=indexed)
