"""Search boundary: embeddings, the Azure AI Search adapter, indexing, and retrieval."""

from app.search.content import content_hash, embedding_text
from app.search.indexer import MessageIndexer
from app.search.protocols import EmbeddingPort, SearchDocument, SearchHit, SearchIndexPort
from app.search.retrieval import SearchService

__all__ = [
    "EmbeddingPort",
    "MessageIndexer",
    "SearchDocument",
    "SearchHit",
    "SearchIndexPort",
    "SearchService",
    "content_hash",
    "embedding_text",
]

