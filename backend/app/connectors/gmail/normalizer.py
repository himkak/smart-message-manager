"""Translate Gmail REST payloads into source-independent domain models."""

import base64
from datetime import UTC, datetime
from email.utils import getaddresses
from html.parser import HTMLParser
from typing import Any

from app.models import Message, MessageSource


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    return {
        str(header["name"]).lower(): str(header["value"])
        for header in payload.get("headers", [])
        if "name" in header and "value" in header
    }


def _decode_body(data: str | None) -> str:
    if not data:
        return ""
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding).decode("utf-8", errors="replace")


def _body_and_attachments(part: dict[str, Any]) -> tuple[str, list[str]]:
    mime_type = part.get("mimeType", "")
    attachment_ids: list[str] = []
    body = part.get("body", {})
    if attachment_id := body.get("attachmentId"):
        attachment_ids.append(str(attachment_id))

    children = [_body_and_attachments(child) for child in part.get("parts", [])]
    child_text = [text for text, _ in children if text]
    for _, ids in children:
        attachment_ids.extend(ids)

    own_text = _decode_body(body.get("data"))
    if mime_type == "text/html" and own_text:
        extractor = _TextExtractor()
        extractor.feed(own_text)
        own_text = " ".join(extractor.parts)
    if mime_type == "text/plain" and own_text:
        return own_text, attachment_ids
    return "\n".join(child_text) or own_text, attachment_ids


def _addresses(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    parsed = tuple(address for _, address in getaddresses([value]) if address)
    return parsed or (value,)


def normalize_gmail_message(raw: dict[str, Any]) -> Message:
    """Normalize one `users.messages.get(format=full)` response."""
    payload = raw.get("payload", {})
    headers = _headers(payload)
    text, attachment_ids = _body_and_attachments(payload)
    sender = headers.get("from", "unknown@gmail.invalid")
    recipients = _addresses(headers.get("to")) + _addresses(headers.get("cc"))
    participants = tuple(dict.fromkeys((sender, *recipients)))

    return Message(
        id=str(raw["id"]),
        source=MessageSource.GMAIL,
        conversation_id=str(raw["threadId"]),
        timestamp=datetime.fromtimestamp(int(raw["internalDate"]) / 1000, tz=UTC),
        sender=sender,
        recipients=recipients,
        subject=headers.get("subject"),
        text=text,
        attachment_ids=tuple(attachment_ids),
        participants=participants,
        metadata={
            "gmail_history_id": raw.get("historyId"),
            "gmail_label_ids": raw.get("labelIds", []),
            "rfc_message_id": headers.get("message-id"),
        },
    )
