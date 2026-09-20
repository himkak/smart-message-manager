"""Small asynchronous Gmail REST client with bounded retry handling."""

import asyncio
from typing import Any

import httpx


class GmailApiError(RuntimeError):
    pass


class GmailHistoryExpiredError(GmailApiError):
    pass


class GmailApiClient:
    base_url = "https://gmail.googleapis.com/gmail/v1/users/me"

    def __init__(self, access_token: str) -> None:
        self._headers = {"Authorization": f"Bearer {access_token}"}

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            for attempt in range(3):
                response = await client.get(f"{self.base_url}{path}", headers=self._headers, params=params)
                if response.status_code == 404 and path.startswith("/history"):
                    raise GmailHistoryExpiredError("The Gmail history cursor is no longer valid.")
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break
                await asyncio.sleep(0.5 * (2**attempt))
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                raise GmailApiError(f"Gmail API request failed: {error.response.status_code}") from error
            return response.json()

    async def profile(self) -> dict[str, Any]:
        return await self._get("/profile")

    async def list_messages(self, page_token: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"maxResults": 100}
        if page_token:
            params["pageToken"] = page_token
        return await self._get("/messages", params=params)

    async def get_message(self, message_id: str) -> dict[str, Any]:
        return await self._get(f"/messages/{message_id}", params={"format": "full"})

    async def list_history(self, start_history_id: str, page_token: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"startHistoryId": start_history_id, "historyTypes": "messageAdded"}
        if page_token:
            params["pageToken"] = page_token
        return await self._get("/history", params=params)
