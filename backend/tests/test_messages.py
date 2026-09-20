from datetime import UTC, datetime

from app.models import Conversation, Message, MessageSource


def test_message_normalizes_duplicate_participants() -> None:
    message = Message(
        id="gmail-message-1",
        source=MessageSource.GMAIL,
        conversation_id="gmail-thread-1",
        timestamp=datetime(2026, 9, 12, tzinfo=UTC),
        sender=" rahul@example.com ",
        recipients=["me@example.com", "me@example.com"],
        participants=["rahul@example.com", "me@example.com", "rahul@example.com"],
        text="Goa hotel looks good.",
    )

    assert message.sender == "rahul@example.com"
    assert message.recipients == ("me@example.com",)
    assert message.participants == ("rahul@example.com", "me@example.com")


def test_conversation_supports_future_sources_without_connector_implementation() -> None:
    conversation = Conversation(id="sms-thread-1", source=MessageSource.SMS)

    assert conversation.source is MessageSource.SMS

