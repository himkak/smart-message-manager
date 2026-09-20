# Current implementation state

Last reviewed: 2026-09-20

## Completed phases

| Phase | Deliverable | Status |
| --- | --- | --- |
| 0 | Architecture, ADRs, configuration, FastAPI health endpoint, project scaffold | Complete |
| 1 | Canonical models and idempotent local SQLite repositories (sync-state and search-index-state bookkeeping) | Complete |
| 2 | Gmail read-only OAuth, message normalization, initial/incremental synchronization straight into Azure AI Search | Complete and validated with a synthetic test mailbox |
| 3 | Azure AI Search hybrid retrieval | Complete and validated live against the configured dev Azure AI Search index and Azure OpenAI embedding deployment |
| 4 | Azure OpenAI RAG, no-evidence handling, structured citations | Complete and validated live against the configured `gpt-4.1-mini` chat deployment |
| 5 | Minimal React/TypeScript UI and end-to-end validation | Complete and validated live with Playwright against the real backend and Azure resources |

Phase 3 details: embeddings are generated from `subject + sender + text` via `AzureEmbeddingClient` (Azure OpenAI `text-embedding-3-small`, 1536 dimensions). `AzureSearchIndex` creates/updates the `smart-messages-v1` index (scalar fields plus `Collection(Edm.String)` fields for `recipients`/`participants`, and a vector field on an HNSW profile) and performs hybrid keyword+vector search. `MessageIndexer` hashes `subject + sender + text` per message and skips re-embedding/re-uploading unchanged content, tracked in a local `search_index_state` SQLite table (bookkeeping only, not message content). `GmailConnector` calls `MessageIndexer` directly during sync (see Phase 2 update below) — messages are never persisted to a local SQLite message store. `POST /api/search` runs hybrid retrieval and returns `503` if Azure Search/OpenAI settings are not configured.

**Update (2026-09-20):** Gmail sync no longer stores message/conversation data in SQLite at all. `GmailConnector` now depends on `MessageIndexer` instead of `MessageRepository`/`ConversationRepository`: it normalizes each fetched Gmail message and passes the batch straight to the indexer, which embeds and uploads it to Azure AI Search in the same `/api/sync/gmail` call (`SyncResult` now also reports `indexed`). This closes a gap where synced mail sat unembedded until a separate manual step ran. The manual `POST /api/search/index` endpoint and the "Index local messages" UI button were removed since they're no longer needed. SQLite now only tracks the Gmail history cursor (`sync_state`) and per-message content hash (`search_index_state`) — no raw message content is stored locally.

Phase 4 details: `RagService` retrieves the top-N hybrid search hits for a question (no hits short-circuits to a fixed no-evidence answer without calling the model), builds a numbered evidence prompt from each hit's `message_id`, `source`, `sender`, `subject`, `timestamp`, and text, and calls `AzureChatClient` (Azure OpenAI chat, structured `json_schema` output). The model must return `answer`, `has_evidence`, and `citations` (each with `message_id`/`source`/`quote`). Any citation whose `message_id` was not actually retrieved is dropped; if no valid citations remain, the response is downgraded to the same fixed no-evidence answer regardless of what the model claimed, so citations are always independently verifiable. `POST /api/chat` exposes this and returns `503` if Azure Search/OpenAI embedding/chat settings are not configured.

Phase 5 details: `frontend/` is a Vite + React + TypeScript SPA with three components — `StatusBar` (Gmail connection/sync, now also reporting how many messages were indexed per sync), `SearchPanel` (hybrid search), and `ChatPanel` (ask + evidence badge + citations) — talking to the backend via a typed `src/api.ts` client. The backend gained a `FRONTEND_ORIGIN`-driven `CORSMiddleware` so the Vite dev server (port 5173) can call it. Playwright end-to-end tests (`frontend/e2e/app.spec.ts`) start both the Vite dev server and the backend automatically and exercise real flows: connection status, search, a grounded question with citations, and a no-evidence question — all live against the configured Azure resources.

## Active phase

None. All planned V1 phases (0–5) are complete.

## Explicitly out of scope for V1 implementation so far

WhatsApp, SMS, sending or drafting messages, calendar actions, autonomous agent actions, attachment-content extraction, Cosmos DB, Azure Blob Storage, Entra authentication, Key Vault, and production deployment.
