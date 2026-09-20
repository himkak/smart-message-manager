"""Ports and data contracts for evidence-grounded Q&A over retrieved messages."""

from dataclasses import dataclass
from typing import Protocol

from app.models import MessageSource


@dataclass(frozen=True)
class Citation:
    """A single evidence reference backing (part of) an answer."""

    message_id: str
    source: MessageSource
    quote: str


@dataclass(frozen=True)
class ChatAnswer:
    """A structured, citation-backed answer, or a no-evidence response."""

    answer: str
    has_evidence: bool
    citations: tuple[Citation, ...] = ()


class ChatPort(Protocol):
    """Completes a chat prompt and returns raw JSON text matching the answer schema."""

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str: ...
