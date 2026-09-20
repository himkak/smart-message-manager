"""SQLite repository adapters for local development.

Each adapter works with the source-independent domain models and uses source-scoped
keys, so connector retries can safely upsert the same provider message.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import aiosqlite

from app.models import Conversation, Message, MessageSource

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS conversations (
    source TEXT NOT NULL,
    id TEXT NOT NULL,
    subject TEXT,
    started_at TEXT,
    last_message_at TEXT,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (source, id)
);

CREATE TABLE IF NOT EXISTS conversation_participants (
    source TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    participant TEXT NOT NULL,
    PRIMARY KEY (source, conversation_id, participant),
    FOREIGN KEY (source, conversation_id)
        REFERENCES conversations(source, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    source TEXT NOT NULL,
    id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    sender TEXT NOT NULL,
    recipients_json TEXT NOT NULL,
    subject TEXT,
    text TEXT NOT NULL,
    attachment_ids_json TEXT NOT NULL,
    participants_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (source, id)
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages (source, conversation_id, timestamp);

CREATE TABLE IF NOT EXISTS sync_states (
    source TEXT NOT NULL PRIMARY KEY,
    cursor TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_index_state (
    source TEXT NOT NULL,
    id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    indexed_at TEXT NOT NULL,
    PRIMARY KEY (source, id)
);
"""


def _encode(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _decode(value: str) -> object:
    return json.loads(value)


def _as_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


def _message_from_row(row: aiosqlite.Row) -> Message:
    return Message(
        id=row["id"],
        source=MessageSource(row["source"]),
        conversation_id=row["conversation_id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        sender=row["sender"],
        recipients=tuple(_decode(row["recipients_json"])),
        subject=row["subject"],
        text=row["text"],
        attachment_ids=tuple(_decode(row["attachment_ids_json"])),
        participants=tuple(_decode(row["participants_json"])),
        metadata=dict(_decode(row["metadata_json"])),
    )


class SQLiteDatabase:
    """Small connection factory that initializes an on-disk SQLite schema on demand."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = str(database_path)

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        async with aiosqlite.connect(self._database_path) as connection:
            connection.row_factory = aiosqlite.Row
            await connection.executescript(_SCHEMA)
            yield connection


class SQLiteMessageRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    async def upsert(self, message: Message) -> Message:
        """Insert or replace a message using its stable `(source, id)` identity."""
        async with self._database.connection() as connection:
            await connection.execute(
                """
                INSERT INTO messages (
                    source, id, conversation_id, timestamp, sender, recipients_json,
                    subject, text, attachment_ids_json, participants_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, id) DO UPDATE SET
                    conversation_id = excluded.conversation_id,
                    timestamp = excluded.timestamp,
                    sender = excluded.sender,
                    recipients_json = excluded.recipients_json,
                    subject = excluded.subject,
                    text = excluded.text,
                    attachment_ids_json = excluded.attachment_ids_json,
                    participants_json = excluded.participants_json,
                    metadata_json = excluded.metadata_json
                """,
                (
                    message.source.value,
                    message.id,
                    message.conversation_id,
                    message.timestamp.isoformat(),
                    message.sender,
                    _encode(message.recipients),
                    message.subject,
                    message.text,
                    _encode(message.attachment_ids),
                    _encode(message.participants),
                    _encode(message.metadata),
                ),
            )
            await connection.commit()
        return message

    async def get(self, source: MessageSource, message_id: str) -> Message | None:
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                "SELECT * FROM messages WHERE source = ? AND id = ?", (source.value, message_id)
            )
            row = await cursor.fetchone()
        return _message_from_row(row) if row is not None else None

    async def list_for_conversation(
        self, source: MessageSource, conversation_id: str, *, limit: int = 100
    ) -> list[Message]:
        if limit <= 0:
            return []
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT * FROM messages
                WHERE source = ? AND conversation_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (source.value, conversation_id, limit),
            )
            rows = await cursor.fetchall()
        return [_message_from_row(row) for row in rows]

    async def list_all(self, source: MessageSource, *, limit: int = 1000) -> list[Message]:
        if limit <= 0:
            return []
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                "SELECT * FROM messages WHERE source = ? ORDER BY timestamp ASC LIMIT ?",
                (source.value, limit),
            )
            rows = await cursor.fetchall()
        return [_message_from_row(row) for row in rows]


class SQLiteConversationRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    async def upsert(self, conversation: Conversation) -> Conversation:
        async with self._database.connection() as connection:
            await connection.execute("BEGIN")
            await connection.execute(
                """
                INSERT INTO conversations (source, id, subject, started_at, last_message_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, id) DO UPDATE SET
                    subject = excluded.subject,
                    started_at = excluded.started_at,
                    last_message_at = excluded.last_message_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    conversation.source.value,
                    conversation.id,
                    conversation.subject,
                    conversation.started_at.isoformat() if conversation.started_at else None,
                    conversation.last_message_at.isoformat() if conversation.last_message_at else None,
                    _encode(conversation.metadata),
                ),
            )
            await connection.execute(
                "DELETE FROM conversation_participants WHERE source = ? AND conversation_id = ?",
                (conversation.source.value, conversation.id),
            )
            await connection.executemany(
                """
                INSERT INTO conversation_participants (source, conversation_id, participant)
                VALUES (?, ?, ?)
                """,
                [(conversation.source.value, conversation.id, participant) for participant in conversation.participants],
            )
            await connection.commit()
        return conversation

    async def get(self, source: MessageSource, conversation_id: str) -> Conversation | None:
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                "SELECT * FROM conversations WHERE source = ? AND id = ?",
                (source.value, conversation_id),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            participant_cursor = await connection.execute(
                """
                SELECT participant FROM conversation_participants
                WHERE source = ? AND conversation_id = ?
                ORDER BY participant ASC
                """,
                (source.value, conversation_id),
            )
            participants = tuple(item["participant"] for item in await participant_cursor.fetchall())

        return Conversation(
            id=row["id"],
            source=MessageSource(row["source"]),
            participants=participants,
            subject=row["subject"],
            started_at=_as_datetime(row["started_at"]),
            last_message_at=_as_datetime(row["last_message_at"]),
            metadata=dict(_decode(row["metadata_json"])),
        )


class SQLiteSyncStateRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    async def get_cursor(self, source: MessageSource) -> str | None:
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                "SELECT cursor FROM sync_states WHERE source = ?", (source.value,)
            )
            row = await cursor.fetchone()
        return str(row["cursor"]) if row is not None else None

    async def set_cursor(self, source: MessageSource, cursor: str, *, updated_at: datetime) -> None:
        async with self._database.connection() as connection:
            await connection.execute(
                """
                INSERT INTO sync_states (source, cursor, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    cursor = excluded.cursor,
                    updated_at = excluded.updated_at
                """,
                (source.value, cursor, updated_at.isoformat()),
            )
            await connection.commit()


class SQLiteSearchIndexStateRepository:
    """Records the last-indexed content hash per message to skip unchanged re-embedding."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    async def get_hash(self, source: MessageSource, message_id: str) -> str | None:
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                "SELECT content_hash FROM search_index_state WHERE source = ? AND id = ?",
                (source.value, message_id),
            )
            row = await cursor.fetchone()
        return str(row["content_hash"]) if row is not None else None

    async def set_hash(
        self, source: MessageSource, message_id: str, content_hash: str, *, indexed_at: datetime
    ) -> None:
        async with self._database.connection() as connection:
            await connection.execute(
                """
                INSERT INTO search_index_state (source, id, content_hash, indexed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source, id) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    indexed_at = excluded.indexed_at
                """,
                (source.value, message_id, content_hash, indexed_at.isoformat()),
            )
            await connection.commit()
