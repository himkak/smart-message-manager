"""Azure OpenAI chat client used for structured, citation-backed RAG answers."""

import logging

from openai import AsyncAzureOpenAI

from app.observability import truncate
from app.rag.prompting import ANSWER_RESPONSE_SCHEMA

logger = logging.getLogger(__name__)


class AzureChatClient:
    """Wraps the Azure OpenAI chat completions API behind the `ChatPort` protocol."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str = "2024-10-21",
    ) -> None:
        self._deployment = deployment
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint, api_key=api_key, api_version=api_version
        )

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        logger.info(
            "[AzureChatClient] request: deployment=%s system_prompt=%s user_prompt=%s",
            self._deployment,
            truncate(system_prompt, 300),
            truncate(user_prompt, 2000),
        )
        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=ANSWER_RESPONSE_SCHEMA,
            temperature=0,
            max_tokens=2000,
        )
        choice = response.choices[0]
        logger.info(
            "[AzureChatClient] response: finish_reason=%s usage=%s",
            choice.finish_reason,
            response.usage,
        )
        if choice.finish_reason == "length":
            raise ValueError(
                "Azure OpenAI chat completion was truncated before finishing (finish_reason=length)."
            )
        content = choice.message.content
        if content is None:
            raise ValueError("Azure OpenAI chat completion returned no content.")
        logger.debug("[AzureChatClient] response content: %s", truncate(content, 2000))
        return content

    async def close(self) -> None:
        await self._client.close()
