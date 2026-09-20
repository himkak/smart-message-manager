from datetime import UTC, datetime

from app.models import Message, MessageSource
from app.repositories.sqlite import SQLiteDatabase, SQLiteSearchIndexStateRepository
from app.search.indexer import MessageIndexer
from app.search.protocols import SearchDocument


def make_message(*, message_id: str = "message-1", text: str = "Book Coral Bay by Friday.") -> Message:
    return Message(
        id=message_id,
        source=MessageSource.GMAIL,
        conversation_id="thread-1",
        timestamp=datetime(2026, 9, 12, 9, 30, tzinfo=UTC),
        sender="rahul@example.com",
        subject="Goa trip",
        text=text,
    )


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [float(len(text)), 0.0]


class FakeSearchIndex:
    def __init__(self) -> None:
        self.uploaded: list[SearchDocument] = []

    async def ensure_index(self) -> None:
        pass

    async def upload_documents(self, documents: list[SearchDocument]) -> None:
        self.uploaded.extend(documents)

    async def hybrid_search(self, query: str, query_vector: list[float], *, top: int = 10) -> list:
        return []


async def test_index_messages_embeds_and_uploads_new_content(tmp_path) -> None:
    index_state = SQLiteSearchIndexStateRepository(SQLiteDatabase(tmp_path / "search.db"))
    embeddings = FakeEmbeddingClient()
    search_index = FakeSearchIndex()
    indexer = MessageIndexer(search_index=search_index, embeddings=embeddings, index_state=index_state)

    indexed = await indexer.index_messages([make_message()])

    assert indexed == 1
    assert len(search_index.uploaded) == 1
    assert search_index.uploaded[0].key == "gmail_message-1"
    assert embeddings.calls == ["Goa trip\nrahul@example.com\nBook Coral Bay by Friday."]


async def test_index_messages_skips_unchanged_content(tmp_path) -> None:
    index_state = SQLiteSearchIndexStateRepository(SQLiteDatabase(tmp_path / "search.db"))
    embeddings = FakeEmbeddingClient()
    search_index = FakeSearchIndex()
    indexer = MessageIndexer(search_index=search_index, embeddings=embeddings, index_state=index_state)

    await indexer.index_messages([make_message()])
    indexed_again = await indexer.index_messages([make_message()])

    assert indexed_again == 0
    assert len(embeddings.calls) == 1
    assert len(search_index.uploaded) == 1


async def test_index_messages_reembeds_changed_content(tmp_path) -> None:
    index_state = SQLiteSearchIndexStateRepository(SQLiteDatabase(tmp_path / "search.db"))
    embeddings = FakeEmbeddingClient()
    search_index = FakeSearchIndex()
    indexer = MessageIndexer(search_index=search_index, embeddings=embeddings, index_state=index_state)

    await indexer.index_messages([make_message()])
    indexed_again = await indexer.index_messages([make_message(text="Updated: book Coral Bay today.")])

    assert indexed_again == 1
    assert len(search_index.uploaded) == 2
