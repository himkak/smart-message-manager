"""Endpoint for hybrid keyword+vector search over indexed messages.

Messages are embedded and uploaded to Azure AI Search automatically as part of
Gmail sync (see `app/api/gmail.py`); there is no separate manual indexing step.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models import Message
from app.observability import truncate
from app.search.retrieval import SearchService

logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top: int = Field(default=10, ge=1, le=50)


class SearchResultItem(BaseModel):
    score: float
    message: Message


class SearchResponse(BaseModel):
    results: list[SearchResultItem]


def create_search_router(
    *,
    search_service: SearchService | None,
    search_is_configured: bool,
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["search"])

    @router.post("/search", response_model=SearchResponse)
    async def search(request: SearchRequest) -> SearchResponse:
        logger.info(
            "[API /api/search] received query=%r top=%d", truncate(request.query, 200), request.top
        )
        if not search_is_configured or search_service is None:
            logger.warning("[API /api/search] rejected: search is not configured (missing .env values)")
            raise HTTPException(
                status_code=503,
                detail="Set Azure AI Search and Azure OpenAI embedding values in .env.",
            )
        hits = await search_service.search(request.query, top=request.top)
        logger.info("[API /api/search] responding: results=%d", len(hits))
        return SearchResponse(
            results=[SearchResultItem(score=hit.score, message=hit.message) for hit in hits]
        )

    return router
