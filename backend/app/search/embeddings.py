"""Azure OpenAI embedding client used to convert message text into vectors."""

import logging

from openai import AsyncAzureOpenAI

from app.observability import truncate

logger = logging.getLogger(__name__)


class AzureEmbeddingClient:
    """Wraps the Azure OpenAI embeddings API behind the `EmbeddingPort` protocol."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str = "2024-06-01",
    ) -> None:
        self._deployment = deployment
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint, api_key=api_key, api_version=api_version
        )

    async def embed(self, text: str) -> list[float]:
        logger.debug(
            "[AzureEmbeddingClient] request: deployment=%s input=%r",
            self._deployment,
            truncate(text, 200),
        )
        response = await self._client.embeddings.create(model=self._deployment, input=text or " ")
        vector = list(response.data[0].embedding)
        logger.debug("[AzureEmbeddingClient] response: %d-dim vector", len(vector))
        return vector

    async def close(self) -> None:
        await self._client.close()
