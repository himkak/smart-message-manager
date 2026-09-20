"""Prompt construction and the structured-output schema for RAG answers.

The system prompt requires the model to answer only from the numbered evidence
block and to cite the message IDs it relied on; `answer_response_schema` enforces
that shape at the API level via Azure OpenAI structured outputs.
"""

from app.search.protocols import SearchHit

NO_EVIDENCE_ANSWER = "I couldn't find any messages that answer this question."

SYSTEM_PROMPT = (
    "You answer questions about the user's personal messages using ONLY the numbered "
    "evidence entries provided in the user message. Never use outside knowledge or "
    "assumptions. Every claim in your answer must be supported by at least one cited "
    "evidence entry. If the evidence does not answer the question, set has_evidence to "
    "false and give an answer explaining that no evidence was found; do not guess. Cite "
    "evidence using the exact message_id and source shown for each entry, and quote the "
    "supporting snippet verbatim from that entry's text. Keep your answer to at most 3 "
    "sentences, cite at most 3 evidence entries, and keep each quote under 200 characters. "
    "Never repeat words, sentences, or citations."
)

_MAX_SNIPPET_LENGTH = 1500


def _snippet(text: str) -> str:
    if len(text) <= _MAX_SNIPPET_LENGTH:
        return text
    return text[:_MAX_SNIPPET_LENGTH] + "…"


def build_user_prompt(question: str, hits: list[SearchHit]) -> str:
    """Number each retrieved message as evidence the model may cite by ID."""
    evidence_blocks = []
    for index, hit in enumerate(hits, start=1):
        message = hit.message
        evidence_blocks.append(
            "\n".join(
                [
                    f"[Evidence {index}]",
                    f"message_id: {message.id}",
                    f"source: {message.source.value}",
                    f"sender: {message.sender}",
                    f"subject: {message.subject or ''}",
                    f"timestamp: {message.timestamp.isoformat()}",
                    f"text: {_snippet(message.text)}",
                ]
            )
        )
    evidence = "\n\n".join(evidence_blocks)
    return f"Question: {question}\n\nEvidence:\n{evidence}"


ANSWER_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "rag_answer",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "has_evidence": {"type": "boolean"},
                "citations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string"},
                            "source": {"type": "string"},
                            "quote": {"type": "string"},
                        },
                        "required": ["message_id", "source", "quote"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["answer", "has_evidence", "citations"],
            "additionalProperties": False,
        },
    },
}
