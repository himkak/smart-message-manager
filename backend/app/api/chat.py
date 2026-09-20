"""Endpoint for evidence-grounded Q&A over indexed messages."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models import MessageSource
from app.observability import truncate
from app.rag.service import RagAnswerError, RagService

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)


class CitationResponse(BaseModel):
    message_id: str
    source: MessageSource
    quote: str


class ChatResponse(BaseModel):
    answer: str
    has_evidence: bool
    citations: list[CitationResponse]


def create_chat_router(*, rag_service: RagService | None, chat_is_configured: bool) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["chat"])

    @router.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        logger.info("[API /api/chat] received question=%r", truncate(request.question, 200))
        if not chat_is_configured or rag_service is None:
            logger.warning("[API /api/chat] rejected: chat is not configured (missing .env values)")
            raise HTTPException(
                status_code=503,
                detail="Set Azure AI Search, Azure OpenAI embedding, and chat values in .env.",
            )
        try:
            result = await rag_service.answer(request.question)
        except RagAnswerError as error:
            logger.error("[API /api/chat] RagService failed: %s", error)
            raise HTTPException(
                status_code=502,
                detail="The AI service returned an unexpected response. Please try again.",
            ) from error
        logger.info(
            "[API /api/chat] responding: has_evidence=%s citations=%d",
            result.has_evidence,
            len(result.citations),
        )
        return ChatResponse(
            answer=result.answer,
            has_evidence=result.has_evidence,
            citations=[
                CitationResponse(message_id=c.message_id, source=c.source, quote=c.quote)
                for c in result.citations
            ],
        )

    return router
