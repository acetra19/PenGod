# PenGod

Collaborative AI agent stack for **authorized** bug bounty research: RAG over disclosure-style reports, multi-agent orchestration (LangGraph), Qdrant, FastAPI.

Requires **Python 3.10+**.

## Setup

```bash
cd c:\PenGod
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
```

Optional: `pip install -e ".[dev,agents]"` for an explicit `langchain-core` pin alongside LangGraph.

Copy `.env.example` to `.env` and adjust Qdrant and embedding settings.

### Docker

**Development compose** (`docker-compose.yml`): exposes **Qdrant 6333** and **API 8000** on the host (easy debugging).

```bash
mkdir -p data
docker compose up -d --build
```

**Production-style compose** (`docker-compose.prod.yml`): **Qdrant has no host port** (only reachable inside the Docker network). **PenGod** is not published; **Nginx** is mapped to host port **8080** (not 80, so it does not clash with an existing web server on the VPS).

```bash
mkdir -p data
docker compose -f docker-compose.prod.yml up -d --build
```

- Ingest (same `./data` mount):  
  `docker compose -f docker-compose.prod.yml exec pengod pengh ingest /data/Casestudies.txt`
- Call the API via Nginx: `http://YOUR_SERVER:8080/v1/search?q=...` and `http://YOUR_SERVER:8080/health`.
- TLS: place certs under `./deploy/certs/`, uncomment the `443` port and volume in `docker-compose.prod.yml`, and the second `server` block in `deploy/nginx.conf` (or terminate TLS with a host-level reverse proxy / CDN instead).
- First start may take minutes while **FastEmbed** downloads the model; `HF_HOME` is persisted in a Docker volume.

With Compose, `QDRANT_URL=http://qdrant:6333` is set automatically. Override via `.env` only if you need extra variables.

### Qdrant

Run a Qdrant instance locally (for example Docker: `docker run -p 6333:6333 qdrant/qdrant`). The app and ingest expect `QDRANT_URL` (default `http://localhost:6333`).

### Ingest case exports (`Casestudies.txt` format)

After Qdrant is up, load your text export (blocks starting with `Case N`, headers like `Title:`, then `Details:`):

```bash
pengh ingest path\to\Casestudies.txt
```

Or: `python -m pengod.cli ingest path\to\Casestudies.txt`

This parses cases, runs the context refiner, chunks text, embeds with **FastEmbed** (`BAAI/bge-small-en-v1.5`, 384 dims by default), and upserts into the configured collection.

### Search

CLI:

```bash
pengh search "stored xss attachment preview"
```

API (with ingested data):

- `GET /v1/search?q=...&limit=8`

### Engagement run (authorized in-scope URL)

`POST /v1/engagement/run` — HTTP probe (SSRF-guarded) + RAG hits for patterns. **Only use URLs you are allowed to test** (program scope).

```bash
curl -sS -X POST http://127.0.0.1:8080/v1/engagement/run \
  -H "Content-Type: application/json" \
  -d '{"target_url":"https://example.com","rag_limit":5}'
```

If `PENGOD_API_KEY` is set in the environment, send header `X-API-Key: <your-key>`.

### Strategist run (probe → RAG → Ollama report)

`POST /v1/strategist/run` runs a **LangGraph** pipeline per URL: HTTP probe (same SSRF guards as engagement) → semantic search → **Ollama** `/api/chat` to produce a markdown-style strategy report. Configure `OLLAMA_BASE_URL`, `STRATEGIST_MODEL`, and `STRATEGIST_RAG_LIMIT` in the environment. The API container must reach Ollama (e.g. on the host: `OLLAMA_BASE_URL=http://host.docker.internal:11434` on Windows/Mac Docker Desktop, or run Ollama on the same network as the API).

Request body:

- `target_urls`: array of `https://...` URLs (required), or legacy single `target_url`
- optional `program_scope`: free text (bug bounty scope) — blended into RAG and passed to the Strategist so suggestions stay aligned

Response: `runs` is an array of per-URL results (`probe`, `rag_query`, `rag_hits`, `strategist_report`, `pipeline_error`).

```bash
curl -sS -X POST http://127.0.0.1:8080/v1/strategist/run \
  -H "Content-Type: application/json" \
  -d '{"target_urls":["https://example.com"],"program_scope":"In scope: example.com web app only."}'
```

### Web UI (Streamlit)

Install the UI extra, then point the browser at the app (API must be running — local or VPS).

```bash
pip install -e ".[ui]"
streamlit run pengod/ui/app.py
```

In the sidebar set **API base URL** (e.g. `http://127.0.0.1:8000` or `http://YOUR_VPS_IP:8080`). Optional: **X-API-Key** if the server has `PENGOD_API_KEY` set.

**Assistant LLM:** choose **Groq (cloud)** or **Ollama (local)**. For Groq, set `GROQ_API_KEY` in the environment before starting Streamlit, or paste the key in the sidebar (session only). Get a key from [Groq Console](https://console.groq.com/) — never commit keys or paste them in public chats.

Tabs: **Agent run** (scope + URLs → Strategist per URL), **Semantic search**, **Engagement run** (probe + RAG only), **Assistant** (chat with optional RAG grounding). The Streamlit sidebar **Ollama URL** applies to the Assistant tab only; the Strategist uses `OLLAMA_BASE_URL` on the API server.

### Run the API

```bash
uvicorn pengod.api.app:app --reload --host 127.0.0.1 --port 8000
```

- Root: `GET /` — service info  
- Health: `GET /health` — includes Qdrant reachability (`status` is `degraded` if Qdrant is down unless `QDRANT_STRICT=true`, which fails startup)

## Package layout

- `pengod/api/` — FastAPI app (`pengod.api.app:app`)
- `pengod/agents/` — LangGraph (`build_research_stub_graph`, Strategist pipeline)
- `pengod/llm/` — Ollama async client for Strategist
- `pengod/ingest/` — Case-study parser, chunking, embeddings, Qdrant ingest pipeline
- `pengod/schemas/` — Pydantic models (e.g. vulnerability reports)
- `pengod/rag/` — Qdrant utilities, context refinement, semantic search
- `pengod/recon/` — HTTP probe + SSRF checks for engagement flow

All user-facing strings in the app/CLI are **English**.
