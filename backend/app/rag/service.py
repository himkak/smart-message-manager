"""Evidence-grounded Q&A: retrieve messages, prompt the model, then validate citations.

Citations the model returns are cross-checked against the actually retrieved message
IDs. Any citation referencing a message that was not retrieved is dropped; if that
leaves no valid citations, the answer is downgraded to a safe no-evidence response
rather than trusting an unverifiable claim.
"""

import json
import logging

from app.models import MessageSource
from app.observability import truncate
from app.rag.prompting import NO_EVIDENCE_ANSWER, SYSTEM_PROMPT, build_user_prompt
from app.rag.protocols import ChatAnswer, ChatPort, Citation
from app.search.retrieval import SearchService

logger = logging.getLogger(__name__)


class RagAnswerError(RuntimeError):
    """Raised when the model response cannot be parsed into a structured answer."""


class RagService:
    def __init__(self, *, search: SearchService, chat: ChatPort, top: int = 8) -> None:
        self._search = search
        self._chat = chat
        self._top = top

    async def answer(self, question: str) -> ChatAnswer:
        logger.info("[RagService] question=%r", truncate(question, 200))
        hits = await self._search.search(question, top=self._top)
        if not hits:
            logger.info("[RagService] no search hits; returning no-evidence answer without calling the model")
            return ChatAnswer(answer=NO_EVIDENCE_ANSWER, has_evidence=False)

        retrieved_ids = {hit.message.id for hit in hits}
        logger.info("[RagService] retrieved %d evidence message(s): %s", len(hits), sorted(retrieved_ids))

        user_prompt = build_user_prompt(question, hits)
        logger.debug("[RagService] prompt sent to model: %s", truncate(user_prompt, 2000))
        try:
            raw_response = await self._chat.complete(
                system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt
            )
        except ValueError as error:
            logger.error("[RagService] chat model call failed: %s", error)
            raise RagAnswerError("The model did not return a usable response.") from error
        logger.debug("[RagService] raw model response: %s", truncate(raw_response, 2000))

        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as error:
            logger.error(
                "[RagService] model response was not valid JSON (%s); response=%s",
                error,
                truncate(raw_response, 500),
            )
            raise RagAnswerError("The model response was not valid JSON.") from error

        try:
            answer_text = str(payload["answer"])
            has_evidence = bool(payload["has_evidence"])
            raw_citations = payload["citations"]
        except (KeyError, TypeError) as error:
            logger.error("[RagService] model response did not match the answer schema: %s", error)
            raise RagAnswerError("The model response did not match the answer schema.") from error

        citations = []
        dropped = 0
        for item in raw_citations:
            if not isinstance(item, dict) or str(item.get("message_id")) not in retrieved_ids:
                dropped += 1
                continue
            try:
                citations.append(
                    Citation(
                        message_id=str(item["message_id"]),
                        source=MessageSource(item["source"]),
                        quote=str(item["quote"]),
                    )
                )
            except (KeyError, ValueError):
                dropped += 1
                continue
        citations = tuple(citations)
        if dropped:
            logger.warning(
                "[RagService] dropped %d citation(s) not matching a retrieved message_id", dropped
            )

        if not citations:
            logger.info(
                "[RagService] no valid citations remained; downgrading to no-evidence answer "
                "(model claimed has_evidence=%s)",
                payload.get("has_evidence"),
            )
            return ChatAnswer(answer=NO_EVIDENCE_ANSWER, has_evidence=False)
        logger.info(
            "[RagService] returning answer: has_evidence=%s citations=%d",
            has_evidence,
            len(citations),
        )
        return ChatAnswer(answer=answer_text, has_evidence=has_evidence, citations=citations)
