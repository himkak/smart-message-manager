"""RAG boundary: retrieval-grounded prompting, structured citations, and no-evidence handling."""

from app.rag.protocols import ChatAnswer, ChatPort, Citation
from app.rag.service import RagAnswerError, RagService

__all__ = [
    "ChatAnswer",
    "ChatPort",
    "Citation",
    "RagAnswerError",
    "RagService",
]

