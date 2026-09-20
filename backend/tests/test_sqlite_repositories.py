from datetime import UTC, datetime

from app.models import Conversation, Message, MessageSource
from app.repositories.sqlite import (
    SQLiteConversationRepository,
    SQLiteDatabase,
    SQLiteMessageRepository,
    SQLiteSyncStateRepository,
)


def make_message(*, text: str = "Initial Goa plan") -> Message:
    return Message(
        id="message-1",
        source=MessageSource.GMAIL,
        conversation_id="thread-1",
        timestamp=datetime(2026, 9, 12, 9, 30, tzinfo=UTC),
        sender="rahul@example.com",
        recipients=("me@example.com",),
        subject="Goa trip",
        text=text,
        participants=("rahul@example.com", "me@example.com"),
        metadata={"provider_label": "INBOX"},
    )


async def test_message_upsert_is_idempotent_and_preserves_source_scope(tmp_path) -> None:
    repository = SQLiteMessageRepository(SQLiteDatabase(tmp_path / "messages.db"))

    await repository.upsert(make_message())
    await repository.upsert(make_message(text="Updated Goa plan"))

    stored = await repository.get(MessageSource.GMAIL, "message-1")
    assert stored is not None
    assert stored.text == "Updated Goa plan"
    assert await repository.get(MessageSource.SMS, "message-1") is None
    assert len(await repository.list_for_conversation(MessageSource.GMAIL, "thread-1")) == 1


async def test_conversation_and_participants_round_trip(tmp_path) -> None:
    repository = SQLiteConversationRepository(SQLiteDatabase(tmp_path / "messages.db"))
    conversation = Conversation(
        id="thread-1",
        source=MessageSource.GMAIL,
        participants=("me@example.com", "rahul@example.com"),
        subject="Goa trip",
        started_at=datetime(2026, 9, 12, tzinfo=UTC),
    )

    await repository.upsert(conversation)

    stored = await repository.get(MessageSource.GMAIL, "thread-1")
    assert stored is not None
    assert stored.id == conversation.id
    assert stored.participants == ("me@example.com", "rahul@example.com")


async def test_sync_cursor_is_saved_per_source(tmp_path) -> None:
    repository = SQLiteSyncStateRepository(SQLiteDatabase(tmp_path / "messages.db"))

    assert await repository.get_cursor(MessageSource.GMAIL) is None
    await repository.set_cursor(MessageSource.GMAIL, "history-123", updated_at=datetime.now(UTC))

    assert await repository.get_cursor(MessageSource.GMAIL) == "history-123"
    assert await repository.get_cursor(MessageSource.WHATSAPP) is None
