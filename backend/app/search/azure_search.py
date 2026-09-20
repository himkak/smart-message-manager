"""Azure AI Search adapter implementing hybrid keyword + vector retrieval.

The index stores a full projection of each canonical message (source, ids, subject,
sender, recipients, participants, text, timestamp) so retrieval never has to call
back into the local repository, plus a vector embedded from `subject + sender + text`.
"""

import logging
from datetime import datetime

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery

from app.models import Message, MessageSource
from app.observability import truncate
from app.search.protocols import SearchDocument, SearchHit

logger = logging.getLogger(__name__)

# text-embedding-3-small produces 1536-dimensional vectors.
EMBEDDING_DIMENSIONS = 1536
_VECTOR_FIELD = "content_vector"
_ALGORITHM_NAME = "smart-messages-hnsw"
_VECTOR_PROFILE_NAME = "smart-messages-vector-profile"


class AzureSearchIndex:
    """Creates/updates the message index and performs hybrid search against it."""

    def __init__(self, *, endpoint: str, api_key: str, index_name: str) -> None:
        credential = AzureKeyCredential(api_key)
        self._index_name = index_name
        self._index_client = SearchIndexClient(endpoint, credential)
        self._search_client = SearchClient(endpoint, index_name, credential)

    async def ensure_index(self) -> None:
        """Create the index if missing, or update it to match the current schema."""
        vector_search = VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name=_ALGORITHM_NAME)],
            profiles=[
                VectorSearchProfile(
                    name=_VECTOR_PROFILE_NAME, algorithm_configuration_name=_ALGORITHM_NAME
                )
            ],
        )
        fields = [
            SimpleField(name="key", type=SearchFieldDataType.String, key=True),
            SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="message_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="conversation_id", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="subject", type=SearchFieldDataType.String),
            SearchableField(name="sender", type=SearchFieldDataType.String, filterable=True),
            SearchableField(
                name="recipients",
                collection=True,
                filterable=True,
            ),
            SearchableField(
                name="participants",
                collection=True,
                filterable=True,
            ),
            SearchableField(name="text", type=SearchFieldDataType.String),
            SimpleField(
                name="timestamp",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
                sortable=True,
            ),
            SimpleField(name="content_hash", type=SearchFieldDataType.String, filterable=True),
            SearchField(
                name=_VECTOR_FIELD,
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=EMBEDDING_DIMENSIONS,
                vector_search_profile_name=_VECTOR_PROFILE_NAME,
            ),
        ]
        index = SearchIndex(name=self._index_name, fields=fields, vector_search=vector_search)
        await self._index_client.create_or_update_index(index)

    async def upload_documents(self, documents: list[SearchDocument]) -> None:
        if not documents:
            return
        logger.info(
            "[AzureSearchIndex] uploading %d document(s) to index=%s: keys=%s",
            len(documents),
            self._index_name,
            [document.key for document in documents],
        )
        payload = [
            {
                "key": document.key,
                "source": document.source.value,
                "message_id": document.message_id,
                "conversation_id": document.conversation_id,
                "subject": document.subject,
                "sender": document.sender,
                "recipients": list(document.recipients),
                "participants": list(document.participants),
                "text": document.text,
                "timestamp": document.timestamp,
                "content_hash": document.content_hash,
                _VECTOR_FIELD: document.embedding,
            }
            for document in documents
        ]
        await self._search_client.merge_or_upload_documents(payload)

    async def hybrid_search(
        self, query: str, query_vector: list[float], *, top: int = 10
    ) -> list[SearchHit]:
        logger.info(
            "[AzureSearchIndex] hybrid query: index=%s search_text=%r vector_dims=%d top=%d",
            self._index_name,
            truncate(query, 200),
            len(query_vector),
            top,
        )
        vector_query = VectorizedQuery(
            vector=query_vector, k_nearest_neighbors=top, fields=_VECTOR_FIELD
        )
        results = await self._search_client.search(
            search_text=query,
            vector_queries=[vector_query],
            top=top,
            select=[
                "message_id",
                "source",
                "conversation_id",
                "subject",
                "sender",
                "recipients",
                "participants",
                "text",
                "timestamp",
            ],
        )
        hits: list[SearchHit] = []
        async for result in results:
            message = Message(
                id=result["message_id"],
                source=MessageSource(result["source"]),
                conversation_id=result["conversation_id"],
                timestamp=datetime.fromisoformat(result["timestamp"]),
                sender=result["sender"],
                recipients=tuple(result.get("recipients") or ()),
                subject=result.get("subject"),
                text=result.get("text") or "",
                participants=tuple(result.get("participants") or ()),
            )
            hits.append(SearchHit(message=message, score=float(result["@search.score"])))
        logger.info(
            "[AzureSearchIndex] hybrid query returned %d result(s): %s",
            len(hits),
            [(hit.message.id, round(hit.score, 4)) for hit in hits],
        )
        return hits

    async def close(self) -> None:
        await self._search_client.close()
        await self._index_client.close()
