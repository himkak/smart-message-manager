"""Hybrid keyword + vector retrieval over indexed messages."""

import logging

from app.observability import truncate
from app.search.protocols import EmbeddingPort, SearchHit, SearchIndexPort

logger = logging.getLogger(__name__)


class SearchService:
    """Embeds a query and runs hybrid keyword+vector search against the index."""

    def __init__(self, *, search_index: SearchIndexPort, embeddings: EmbeddingPort) -> None:
        self._search_index = search_index
        self._embeddings = embeddings

    async def search(self, query: str, *, top: int = 10) -> list[SearchHit]:
        logger.info("[SearchService] embedding query=%r", truncate(query, 200))
        vector = await self._embeddings.embed(query)
        logger.info(
            "[SearchService] embedded query into %d-dim vector; running hybrid search top=%d",
            len(vector),
            top,
        )
        hits = await self._search_index.hybrid_search(query, vector, top=top)
        logger.info(
            "[SearchService] hybrid search returned %d hits: %s",
            len(hits),
            [(hit.message.id, round(hit.score, 4)) for hit in hits],
        )
        return hits
