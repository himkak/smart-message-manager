from datetime import UTC, datetime

from app.api.search import create_search_router
from app.models import Message, MessageSource
from app.search.protocols import SearchHit
from app.search.retrieval import SearchService
from fastapi import FastAPI
from fastapi.testclient import TestClient


def make_message(*, message_id: str = "message-1") -> Message:
    return Message(
        id=message_id,
        source=MessageSource.GMAIL,
        conversation_id="thread-1",
        timestamp=datetime(2026, 9, 12, 9, 30, tzinfo=UTC),
        sender="rahul@example.com",
        subject="Goa trip",
        text="Book Coral Bay by Friday.",
    )


class FakeEmbeddingClient:
    async def embed(self, text: str) -> list[float]:
        return [1.0, 0.0]


class FakeSearchIndex:
    async def hybrid_search(self, query: str, query_vector: list[float], *, top: int = 10) -> list[SearchHit]:
        return [SearchHit(message=make_message(), score=0.87)]


def build_app(*, configured: bool = True) -> FastAPI:
    if not configured:
        router = create_search_router(search_service=None, search_is_configured=False)
    else:
        search_service = SearchService(search_index=FakeSearchIndex(), embeddings=FakeEmbeddingClient())
        router = create_search_router(search_service=search_service, search_is_configured=True)
    app = FastAPI()
    app.include_router(router)
    return app


def test_search_endpoint_returns_hybrid_hits() -> None:
    response = TestClient(build_app()).post("/api/search", json={"query": "Goa hotel"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["score"] == 0.87
    assert body["results"][0]["message"]["id"] == "message-1"


def test_search_endpoint_requires_configuration() -> None:
    response = TestClient(build_app(configured=False)).post("/api/search", json={"query": "Goa"})

    assert response.status_code == 503
