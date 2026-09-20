"""Google OAuth helpers for local development; tokens stay in an ignored local file."""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"


class OAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class GmailToken:
    access_token: str
    refresh_token: str
    expires_at: str
    email: str | None = None

    @property
    def expires_at_datetime(self) -> datetime:
        return datetime.fromisoformat(self.expires_at)


class LocalGmailTokenStore:
    """Development-only token store. The `tokens/` directory is Git-ignored."""

    def __init__(self, path: str | Path = "tokens/gmail-oauth.json") -> None:
        self._path = Path(path)

    def load(self) -> GmailToken | None:
        if not self._path.exists():
            return None
        return GmailToken(**json.loads(self._path.read_text(encoding="utf-8")))

    def save(self, token: GmailToken) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(token)), encoding="utf-8")
        temporary.replace(self._path)


class GoogleOAuthService:
    def __init__(self, *, client_id: str | None, client_secret: str | None, redirect_uri: str | None) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    @property
    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret and self._redirect_uri)

    def authorization_url(self, state: str) -> str:
        if not self.configured:
            raise OAuthError("Google OAuth is not configured.")
        query = urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "response_type": "code",
                "scope": GMAIL_READONLY_SCOPE,
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
        )
        return f"{_AUTHORIZE_URL}?{query}"

    async def exchange_code(self, code: str) -> GmailToken:
        response = await self._token_request(
            {
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self._redirect_uri,
                "grant_type": "authorization_code",
            }
        )
        refresh_token = response.get("refresh_token")
        if not refresh_token:
            raise OAuthError("Google did not return a refresh token. Revoke access and authorize again.")
        return GmailToken(
            access_token=str(response["access_token"]),
            refresh_token=str(refresh_token),
            expires_at=(datetime.now(UTC) + timedelta(seconds=int(response["expires_in"]))).isoformat(),
        )

    async def refresh_if_needed(self, token: GmailToken) -> GmailToken:
        if token.expires_at_datetime > datetime.now(UTC) + timedelta(seconds=60):
            return token
        response = await self._token_request(
            {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": token.refresh_token,
                "grant_type": "refresh_token",
            }
        )
        return GmailToken(
            access_token=str(response["access_token"]),
            refresh_token=token.refresh_token,
            expires_at=(datetime.now(UTC) + timedelta(seconds=int(response["expires_in"]))).isoformat(),
            email=token.email,
        )

    async def _token_request(self, form: dict[str, str | None]) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(_TOKEN_URL, data=form)
        if response.is_error:
            raise OAuthError("Google OAuth token exchange failed.")
        return response.json()
