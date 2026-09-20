import json
from datetime import UTC, datetime

from app.models import Message, MessageSource
from app.rag.service import RagAnswerError, RagService
from app.search.protocols import SearchHit


def make_message(*, message_id: str = "message-1", text: str = "Confirms Coral Bay by Friday.") -> Message:
    return Message(
        id=message_id,
        source=MessageSource.GMAIL,
        conversation_id="thread-1",
        timestamp=datetime(2026, 9, 12, 9, 30, tzinfo=UTC),
        sender="rahul@example.com",
        subject="Goa trip",
        text=text,
    )


class FakeSearchService:
    def __init__(self, hits: list[SearchHit]) -> None:
        self._hits = hits
        self.last_top: int | None = None

    async def search(self, query: str, *, top: int = 10) -> list[SearchHit]:
        self.last_top = top
        return self._hits


class FakeChatClient:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_user_prompt: str | None = None

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.last_user_prompt = user_prompt
        return self._response


async def test_answer_returns_no_evidence_when_search_finds_nothing() -> None:
    service = RagService(search=FakeSearchService([]), chat=FakeChatClient("{}"))

    result = await service.answer("What hotel did we book?")

    assert result.has_evidence is False
    assert result.citations == ()
    assert "couldn't find" in result.answer.lower()


async def test_answer_returns_validated_citations_for_retrieved_messages() -> None:
    hit = SearchHit(message=make_message(), score=0.9)
    response = json.dumps(
        {
            "answer": "You booked Coral Bay.",
            "has_evidence": True,
            "citations": [
                {"message_id": "message-1", "source": "gmail", "quote": "Confirms Coral Bay by Friday."}
            ],
        }
    )
    service = RagService(search=FakeSearchService([hit]), chat=FakeChatClient(response))

    result = await service.answer("What hotel did we book?")

    assert result.has_evidence is True
    assert result.answer == "You booked Coral Bay."
    assert len(result.citations) == 1
    assert result.citations[0].message_id == "message-1"
    assert result.citations[0].source is MessageSource.GMAIL


async def test_answer_downgrades_to_no_evidence_when_citation_is_hallucinated() -> None:
    hit = SearchHit(message=make_message(), score=0.9)
    response = json.dumps(
        {
            "answer": "You booked Coral Bay.",
            "has_evidence": True,
            "citations": [
                {"message_id": "message-does-not-exist", "source": "gmail", "quote": "made up"}
            ],
        }
    )
    service = RagService(search=FakeSearchService([hit]), chat=FakeChatClient(response))

    result = await service.answer("What hotel did we book?")

    assert result.has_evidence is False
    assert result.citations == ()
    assert "couldn't find" in result.answer.lower()


async def test_answer_raises_when_chat_response_is_not_valid_json() -> None:
    hit = SearchHit(message=make_message(), score=0.9)
    service = RagService(search=FakeSearchService([hit]), chat=FakeChatClient("not json"))

    try:
        await service.answer("What hotel did we book?")
        assert False, "expected RagAnswerError"
    except RagAnswerError:
        pass
