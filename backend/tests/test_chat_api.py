from datetime import UTC, datetime

from app.api.chat import create_chat_router
from app.models import Message, MessageSource
from app.rag.service import RagService
from app.search.protocols import SearchHit
from fastapi import FastAPI
from fastapi.testclient import TestClient


def make_message() -> Message:
    return Message(
        id="message-1",
        source=MessageSource.GMAIL,
        conversation_id="thread-1",
        timestamp=datetime(2026, 9, 12, 9, 30, tzinfo=UTC),
        sender="rahul@example.com",
        subject="Goa trip",
        text="Confirms Coral Bay by Friday.",
    )


class FakeSearchService:
    async def search(self, query: str, *, top: int = 10) -> list[SearchHit]:
        return [SearchHit(message=make_message(), score=0.9)]


class FakeChatClient:
    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        return (
            '{"answer": "You booked Coral Bay.", "has_evidence": true, '
            '"citations": [{"message_id": "message-1", "source": "gmail", '
            '"quote": "Confirms Coral Bay by Friday."}]}'
        )


def build_app(*, configured: bool = True) -> FastAPI:
    rag_service = (
        RagService(search=FakeSearchService(), chat=FakeChatClient()) if configured else None
    )
    router = create_chat_router(rag_service=rag_service, chat_is_configured=configured)
    app = FastAPI()
    app.include_router(router)
    return app


def test_chat_endpoint_returns_grounded_answer_with_citations() -> None:
    response = TestClient(build_app()).post("/api/chat", json={"question": "What hotel did we book?"})

    assert response.status_code == 200
    body = response.json()
    assert body["has_evidence"] is True
    assert body["answer"] == "You booked Coral Bay."
    assert body["citations"] == [
        {"message_id": "message-1", "source": "gmail", "quote": "Confirms Coral Bay by Friday."}
    ]


def test_chat_endpoint_requires_configuration() -> None:
    response = TestClient(build_app(configured=False)).post(
        "/api/chat", json={"question": "What hotel did we book?"}
    )

    assert response.status_code == 503


class BrokenChatClient:
    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        return "not valid json"


def test_chat_endpoint_returns_502_when_model_response_is_unparseable() -> None:
    rag_service = RagService(search=FakeSearchService(), chat=BrokenChatClient())
    router = create_chat_router(rag_service=rag_service, chat_is_configured=True)
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).post("/api/chat", json={"question": "What hotel did we book?"})

    assert response.status_code == 502
