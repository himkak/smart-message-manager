"""FastAPI entry point for Smart Messages Manager."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.chat import create_chat_router
from app.api.gmail import create_gmail_router
from app.api.search import create_search_router
from app.config import get_settings
from app.connectors.gmail.oauth import GoogleOAuthService, LocalGmailTokenStore
from app.rag.chat_client import AzureChatClient
from app.rag.service import RagService
from app.repositories import (
    SQLiteDatabase,
    SQLiteSearchIndexStateRepository,
)
from app.search.azure_search import AzureSearchIndex
from app.search.embeddings import AzureEmbeddingClient
from app.search.indexer import MessageIndexer
from app.search.retrieval import SearchService


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    database_path = settings.database_url.removeprefix("sqlite+aiosqlite:///")
    database = SQLiteDatabase(database_path)

    search_is_configured = bool(
        settings.azure_search_endpoint
        and settings.azure_search_api_key
        and settings.azure_search_index
        and settings.azure_openai_endpoint
        and settings.azure_openai_api_key
        and settings.azure_openai_embedding_deployment
    )

    search_index: AzureSearchIndex | None = None
    embeddings: AzureEmbeddingClient | None = None
    indexer: MessageIndexer | None = None
    search_service: SearchService | None = None
    if search_is_configured:
        assert settings.azure_search_endpoint
        assert settings.azure_search_api_key
        assert settings.azure_search_index
        assert settings.azure_openai_endpoint
        assert settings.azure_openai_api_key
        assert settings.azure_openai_embedding_deployment
        search_index = AzureSearchIndex(
            endpoint=settings.azure_search_endpoint,
            api_key=settings.azure_search_api_key,
            index_name=settings.azure_search_index,
        )
        embeddings = AzureEmbeddingClient(
            endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            deployment=settings.azure_openai_embedding_deployment,
        )
        indexer = MessageIndexer(
            search_index=search_index,
            embeddings=embeddings,
            index_state=SQLiteSearchIndexStateRepository(database),
        )
        search_service = SearchService(search_index=search_index, embeddings=embeddings)

    chat_client: AzureChatClient | None = None
    rag_service: RagService | None = None
    chat_is_configured = search_is_configured and bool(settings.azure_openai_chat_deployment)
    if chat_is_configured:
        assert settings.azure_openai_endpoint
        assert settings.azure_openai_api_key
        assert settings.azure_openai_chat_deployment
        assert search_service is not None
        chat_client = AzureChatClient(
            endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            deployment=settings.azure_openai_chat_deployment,
        )
        rag_service = RagService(search=search_service, chat=chat_client)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if search_index is not None:
            await search_index.ensure_index()
        yield
        if search_index is not None:
            await search_index.close()
        if embeddings is not None:
            await embeddings.close()
        if chat_client is not None:
            await chat_client.close()

    app = FastAPI(title="Smart Messages Manager", version="0.1.0", lifespan=lifespan)
    app.add_middleware(SessionMiddleware, secret_key=settings.app_session_secret, https_only=False)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(
        create_gmail_router(
            database=database,
            oauth=GoogleOAuthService(
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
                redirect_uri=settings.google_redirect_uri,
            ),
            token_store=LocalGmailTokenStore(Path("tokens/gmail-oauth.json")),
            oauth_session_is_safe=settings.oauth_session_is_safe,
            indexer=indexer,
        )
    )
    app.include_router(
        create_search_router(
            search_service=search_service,
            search_is_configured=search_is_configured,
        )
    )
    app.include_router(
        create_chat_router(rag_service=rag_service, chat_is_configured=chat_is_configured)
    )

    @app.get("/health", tags=["operations"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.app_env}

    return app


app = create_app()

