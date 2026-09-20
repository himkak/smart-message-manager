# Smart Messages Manager

A privacy-conscious personal communications application. The target is a single place to search personal messages and ask evidence-grounded questions. V1 begins with Gmail, hybrid Azure AI Search retrieval, and cited RAG answers; it deliberately excludes messaging actions and other data sources.

## Implementation status

Phases 0–5 are complete: the repository contains the architecture, canonical domain models, SQLite-backed sync-state/search-index-state tracking, Gmail read-only OAuth and ingestion, configuration, FastAPI endpoints, Azure AI Search hybrid retrieval (embeddings and `/api/search`), Azure OpenAI RAG with structured citations and no-evidence handling (`/api/chat`), a minimal React/TypeScript UI (`frontend/`), and both backend and end-to-end tests. See [current implementation state](docs/current-state.md).

## Run the full app locally

Two processes run side by side: the FastAPI backend and the Vite frontend dev server.

**Terminal 1 — backend** (first-time setup shown; see [Local setup](#local-setup) for details):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn app.main:app --app-dir backend --reload
```

**Terminal 2 — frontend**:

```powershell
cd frontend
npm install
npm run dev
```

**Open the UI:** visit `http://localhost:5173`. The backend API and its docs stay available at `http://127.0.0.1:8000` (`/docs`, `/health`).

Search and chat require Azure Search/OpenAI settings in `.env` (see [Configuration](#configuration)); without them, the UI still loads and shows a clear "Set Azure..." error from those panels.

## Local setup

Requires Python 3.12+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn app.main:app --app-dir backend --reload
```

Then visit `http://127.0.0.1:8000/docs` or call `http://127.0.0.1:8000/health`.

Run the tests with:

```powershell
pytest
```

## Frontend

The frontend (`frontend/`) is a minimal Vite + React + TypeScript single-page app: a Gmail connection/sync status bar (`POST /api/sync/gmail` embeds and indexes new mail into Azure AI Search automatically), a search panel (`POST /api/search`), and a chat panel (`POST /api/chat`) that shows the evidence badge and citations returned by the API.

```powershell
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173`. It calls the backend at `http://127.0.0.1:8000` by default; override with a `VITE_API_BASE_URL` environment variable. The backend allows this origin via CORS through the `FRONTEND_ORIGIN` setting (defaults to `http://localhost:5173`; comma-separate multiple origins).

### Access the UI from your phone

Both dev servers only bind to `localhost` by default. To reach them from a phone on the same Wi-Fi/LAN:

1. Find your PC's LAN IP: `ipconfig` (look for `IPv4 Address`, e.g. `192.168.1.7`).
2. Start the backend so it listens on all interfaces: `uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0`.
3. In `.env`, set `FRONTEND_ORIGIN=http://localhost:5173,http://192.168.1.7:5173` (add your LAN IP) and restart the backend.
4. Create `frontend/.env.local` with `VITE_API_BASE_URL=http://192.168.1.7:8000` (your LAN IP) so the phone's browser talks to the backend directly, not `localhost` (which would resolve to the phone itself). `vite.config.ts` already sets `server.host: true`, so `npm run dev` listens on all interfaces too.
5. Allow inbound connections on ports 8000 and 5173 through the Windows Firewall for your private network, if prompted.
6. On the phone, browse to `http://192.168.1.7:5173`.

Google OAuth's redirect URI is fixed to `localhost`, so Gmail connect/sync must still be done from the PC; search and chat work fine from the phone once synced.

Run the Playwright end-to-end tests (they drive the real UI against your real, already-configured backend and Azure resources, starting both dev servers automatically):

```powershell
cd frontend
npx playwright install chromium
npx playwright test
```

## Configuration

Copy `.env.example` to `.env`; do not commit `.env`. The health endpoint runs with no cloud credentials. To use Gmail, set `APP_SESSION_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` in `.env`.

## Request logging / tracing a request

Every layer logs as a request passes through it, so you can follow one request end-to-end in the backend terminal:

- **API layer** (`app/api/chat.py`, `app/api/search.py`) — logs the incoming request and the outgoing response/status.
- **Search layer** (`app/search/retrieval.py`, `app/search/embeddings.py`, `app/search/azure_search.py`) — logs the embedding call, the literal hybrid query sent to Azure AI Search (search text, vector size, top-k), and the returned hit IDs/scores.
- **RAG layer** (`app/rag/service.py`, `app/rag/chat_client.py`) — logs the retrieved evidence IDs, the prompt sent to Azure OpenAI, the model's `finish_reason`/token usage, the raw response, and the final parsed/validated citations or no-evidence decision.

By default (`LOG_LEVEL=INFO` in `.env`) you get a concise summary at each layer. Set `LOG_LEVEL=DEBUG` in `.env` (and restart the backend, since `.env` changes require a restart) to also see full prompts and raw model responses (truncated to a few thousand characters to keep log lines readable).

## Connect a test Gmail account

1. Create a Google Cloud OAuth **Web application** client with the exact redirect URI `http://localhost:8000/api/auth/google/callback`.
2. Add only the synthetic test inbox as an OAuth test user and configure only the `gmail.readonly` scope.
3. Start the backend and open `http://localhost:8000/api/auth/google/start`.
4. Sign in as the test inbox account, not your personal Gmail account, and approve the read-only consent request.
5. Call `POST http://127.0.0.1:8000/api/sync/gmail` from `/docs`; it fetches new mail and embeds/uploads it to Azure AI Search in one step. Inspect `GET /api/sync/status` there.

The local refresh token is written to `tokens/gmail-oauth.json`, which is ignored by Git. Delete that file and revoke app access from the test account to disconnect it.

## Implemented, in order

Azure AI Search hybrid retrieval: Gmail sync (`POST /api/sync/gmail`) embeds each newly synced message (`subject + sender + text`, skipping unchanged content) and uploads it directly to Azure AI Search — there is no separate local message store or manual indexing step. `POST /api/search` runs hybrid keyword+vector search over that index. Both require `AZURE_SEARCH_*` and `AZURE_OPENAI_*` embedding settings in `.env`; without them, `/api/sync/gmail` returns a 503 instead of syncing.

Azure OpenAI RAG: `POST /api/chat` retrieves evidence via search, prompts the configured `AZURE_OPENAI_CHAT_DEPLOYMENT` for a structured JSON answer with citations, and drops (and downgrades to a no-evidence answer) any citation that doesn't reference an actually retrieved message. It requires the same search settings plus `AZURE_OPENAI_CHAT_DEPLOYMENT`.

Frontend: a minimal React/TypeScript UI in `frontend/` that exercises the endpoints above, with Playwright end-to-end tests.

Production deployment for all of this additionally needs Azure Storage, Key Vault, Application Insights, and a Container Apps environment; `infrastructure/main.bicep` remains an intentionally non-deploying placeholder.

## Gmail OAuth and Azure setup

Gmail OAuth uses a Google Cloud OAuth client configured with the redirect URI in `GOOGLE_REDIRECT_URI` and the least-privilege `gmail.readonly` scope. Search uses Azure AI Search and an Azure OpenAI embedding deployment; RAG additionally uses an Azure OpenAI chat deployment (`AZURE_OPENAI_CHAT_DEPLOYMENT`). All are supplied through environment variables. The application sends only retrieved-context text to Azure OpenAI (for embeddings and for chat prompts), never full mailbox contents.

## Privacy model

The design keeps source connectors separate from RAG, uses source-scoped stable IDs for idempotency, and sends an LLM only retrieved context necessary for a question. Production will use Entra authentication, Key Vault, managed identity, audit logging, encryption, retention controls, and deletion support. Any future send/delete/modify action requires explicit confirmation.
