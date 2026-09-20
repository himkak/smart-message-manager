"""Shared logging helpers so full message/prompt/response bodies never flood logs."""


def truncate(text: str | None, limit: int = 300) -> str:
    """Truncate long text for a single log line, keeping a length marker when cut."""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [{len(text)} chars total]"
