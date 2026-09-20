"""Source-independent communication domain models."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageSource(StrEnum):
    GMAIL = "gmail"
    WHATSAPP = "whatsapp"
    SMS = "sms"


class Message(BaseModel):
    """A normalized message; `id` is stable within its source for idempotent ingestion."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    source: MessageSource
    conversation_id: str = Field(min_length=1)
    timestamp: datetime
    sender: str = Field(min_length=1)
    recipients: tuple[str, ...] = ()
    subject: str | None = None
    text: str = ""
    attachment_ids: tuple[str, ...] = ()
    participants: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("sender")
    @classmethod
    def normalize_sender(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("sender must not be blank")
        return normalized

    @field_validator("recipients", "participants", "attachment_ids", mode="before")
    @classmethod
    def normalize_values(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        return tuple(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


class Conversation(BaseModel):
    """A source-independent grouping of messages."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    source: MessageSource
    participants: tuple[str, ...] = ()
    subject: str | None = None
    started_at: datetime | None = None
    last_message_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

