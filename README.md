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

**Production-style compose** (`docker-compose.prod.yml`): **Qdrant has no host port** (only reachable inside the Docker network). **PenGod** is not published; **Nginx** listens on **80** and proxies to the API. Use this on a VPS behind a firewall.

```bash
mkdir -p data
docker compose -f docker-compose.prod.yml up -d --build
```

- Ingest (same `./data` mount):  
  `docker compose -f docker-compose.prod.yml exec pengod pengh ingest /data/Casestudies.txt`
- Call the API via Nginx: `http://YOUR_SERVER/v1/search?q=...` and `http://YOUR_SERVER/health`.
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

### Run the API

```bash
uvicorn pengod.api.app:app --reload --host 127.0.0.1 --port 8000
```

- Root: `GET /` — service info  
- Health: `GET /health` — includes Qdrant reachability (`status` is `degraded` if Qdrant is down unless `QDRANT_STRICT=true`, which fails startup)

## Package layout

- `pengod/api/` — FastAPI app (`pengod.api.app:app`)
- `pengod/agents/` — LangGraph stubs (`build_research_stub_graph`)
- `pengod/ingest/` — Case-study parser, chunking, embeddings, Qdrant ingest pipeline
- `pengod/schemas/` — Pydantic models (e.g. vulnerability reports)
- `pengod/rag/` — Qdrant utilities, context refinement, semantic search

All user-facing strings in the app/CLI are **English**.
