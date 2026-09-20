import base64

from app.connectors.gmail.connector import GmailConnector
from app.connectors.gmail.normalizer import normalize_gmail_message
from app.models import MessageSource
from app.repositories.sqlite import (
    SQLiteDatabase,
    SQLiteSearchIndexStateRepository,
    SQLiteSyncStateRepository,
)
from app.search.indexer import MessageIndexer
from app.search.protocols import SearchDocument


def gmail_message(message_id: str = "message-1", *, text: str = "Book Coral Bay by Friday.") -> dict:
    return {
        "id": message_id,
        "threadId": "thread-1",
        "internalDate": "1789205400000",
        "historyId": "300",
        "labelIds": ["INBOX"],
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "Rahul Mehta <rahul.test@example.com>"},
                {"name": "To", "value": "test.inbox@example.com"},
                {"name": "Subject", "value": "Goa trip — hotel options"},
                {"name": "Message-ID", "value": "<fixture-1@example.com>"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")},
                },
                {"mimeType": "application/pdf", "body": {"attachmentId": "attachment-1"}},
            ],
        },
    }


class FakeGmailClient:
    def __init__(self) -> None:
        self.messages = {"message-1": gmail_message(), "message-2": gmail_message("message-2", text="Deck is due Friday.")}
        self.initial_ids = ["message-1"]
        self.history_ids: list[str] = []
        self.cursor = "300"

    async def profile(self) -> dict:
        return {"historyId": self.cursor, "emailAddress": "test.inbox@example.com"}

    async def list_messages(self, page_token: str | None = None) -> dict:
        return {"messages": [{"id": item} for item in self.initial_ids]}

    async def get_message(self, message_id: str) -> dict:
        return self.messages[message_id]

    async def list_history(self, start_history_id: str, page_token: str | None = None) -> dict:
        return {
            "history": [
                {"messagesAdded": [{"message": {"id": item}}]} for item in self.history_ids
            ]
        }


class FakeSearchIndex:
    def __init__(self) -> None:
        self.uploaded: list[SearchDocument] = []

    async def upload_documents(self, documents: list[SearchDocument]) -> None:
        self.uploaded.extend(documents)

    async def hybrid_search(self, query: str, query_vector: list[float], *, top: int = 10) -> list:
        return []


class FakeEmbeddingClient:
    async def embed(self, text: str) -> list[float]:
        return [1.0, 0.0]


def test_normalizes_body_headers_and_attachments() -> None:
    message = normalize_gmail_message(gmail_message())

    assert message.source is MessageSource.GMAIL
    assert message.sender == "Rahul Mehta <rahul.test@example.com>"
    assert message.subject == "Goa trip — hotel options"
    assert message.text == "Book Coral Bay by Friday."
    assert message.attachment_ids == ("attachment-1",)


async def test_initial_then_incremental_sync_indexes_messages_without_sqlite_storage(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "gmail.db")
    sync_state = SQLiteSyncStateRepository(database)
    search_index = FakeSearchIndex()
    indexer = MessageIndexer(
        search_index=search_index,
        embeddings=FakeEmbeddingClient(),
        index_state=SQLiteSearchIndexStateRepository(database),
    )
    client = FakeGmailClient()
    connector = GmailConnector(client, indexer, sync_state)

    initial = await connector.initial_sync()
    client.history_ids = ["message-1", "message-2", "message-2"]
    client.cursor = "301"
    incremental = await connector.incremental_sync()

    assert initial.messages_processed == 1
    assert initial.indexed == 1
    assert incremental.messages_processed == 2
    assert incremental.cursor == "301"
    # message-1 is unchanged (skipped by content hash); only message-2 is newly indexed.
    assert incremental.indexed == 1
    assert {document.message_id for document in search_index.uploaded} == {"message-1", "message-2"}
    assert await sync_state.get_cursor(MessageSource.GMAIL) == "301"
