"""Deterministic derivation of embedding input and change-detection hashes.

Both the indexer and the search index rely on the same `subject + sender + text`
projection, so changing this module changes what gets embedded and re-indexed.
"""

import hashlib


def embedding_text(*, subject: str | None, sender: str, text: str) -> str:
    """Build the exact string that is embedded for a message."""
    return "\n".join(part for part in (subject, sender, text) if part)


def content_hash(*, subject: str | None, sender: str, text: str) -> str:
    """Stable hash of the embedding input, used to skip unchanged messages."""
    digest_input = embedding_text(subject=subject, sender=sender, text=text)
    return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
