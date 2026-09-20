"""Local-only Gmail OAuth and synchronization endpoints."""

import logging
import secrets

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import RedirectResponse

from app.connectors.gmail.client import GmailApiClient
from app.connectors.gmail.connector import GmailConnector
from app.connectors.gmail.oauth import (
    GmailToken,
    GoogleOAuthService,
    LocalGmailTokenStore,
    OAuthError,
)
from app.models import MessageSource
from app.repositories import SQLiteDatabase, SQLiteSyncStateRepository
from app.search.indexer import MessageIndexer

logger = logging.getLogger(__name__)


def create_gmail_router(
    *,
    database: SQLiteDatabase,
    oauth: GoogleOAuthService,
    token_store: LocalGmailTokenStore,
    oauth_session_is_safe: bool,
    indexer: MessageIndexer | None,
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["gmail"])
    sync_state = SQLiteSyncStateRepository(database)

    def configured_oauth() -> GoogleOAuthService:
        if not oauth.configured or not oauth_session_is_safe:
            raise HTTPException(
                status_code=503,
                detail="Set Google OAuth values and a 32+ character APP_SESSION_SECRET in .env.",
            )
        return oauth

    async def connected_token() -> GmailToken:
        service = configured_oauth()
        token = token_store.load()
        if token is None:
            raise HTTPException(status_code=401, detail="Connect a Gmail test account first.")
        try:
            refreshed = await service.refresh_if_needed(token)
        except OAuthError as error:
            raise HTTPException(status_code=401, detail=str(error)) from error
        if refreshed != token:
            token_store.save(refreshed)
        return refreshed

    @router.get("/auth/google/start")
    async def start_google_authorization(request: Request) -> RedirectResponse:
        state = secrets.token_urlsafe(32)
        request.session["google_oauth_state"] = state
        return RedirectResponse(configured_oauth().authorization_url(state))

    @router.get("/auth/google/callback")
    async def google_authorization_callback(request: Request, code: str, state: str) -> dict[str, str]:
        expected_state = request.session.pop("google_oauth_state", None)
        if not expected_state or not secrets.compare_digest(state, expected_state):
            raise HTTPException(status_code=400, detail="Invalid OAuth state.")
        try:
            token = await configured_oauth().exchange_code(code)
            profile = await GmailApiClient(token.access_token).profile()
        except OAuthError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        token_store.save(
            GmailToken(
                access_token=token.access_token,
                refresh_token=token.refresh_token,
                expires_at=token.expires_at,
                email=str(profile["emailAddress"]),
            )
        )
        return {"status": "connected", "email": str(profile["emailAddress"])}

    @router.post("/sync/gmail")
    async def sync_gmail() -> dict[str, str | int]:
        if indexer is None:
            raise HTTPException(
                status_code=503,
                detail="Set Azure AI Search and Azure OpenAI embedding values in .env before syncing Gmail.",
            )
        logger.info("[API /api/sync/gmail] starting Gmail sync")
        token = await connected_token()
        connector = GmailConnector(GmailApiClient(token.access_token), indexer, sync_state)
        result = await connector.incremental_sync()
        logger.info(
            "[API /api/sync/gmail] sync complete: messages_processed=%d indexed=%d cursor=%s",
            result.messages_processed,
            result.indexed,
            result.cursor,
        )
        return {
            "status": "ok",
            "messages_processed": result.messages_processed,
            "cursor": result.cursor,
            "indexed": result.indexed,
        }

    @router.get("/sync/status")
    async def sync_status() -> dict[str, str | bool | None]:
        token = token_store.load()
        return {
            "connected": token is not None,
            "email": token.email if token else None,
            "cursor": await sync_state.get_cursor(MessageSource.GMAIL),
        }

    return router
