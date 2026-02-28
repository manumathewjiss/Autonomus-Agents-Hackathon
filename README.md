# ReleaseHub Agents (Backend)

This is the backend service for **ReleaseHub Agents**, a safety-first release/version intelligence assistant.

It exposes HTTP APIs that:
- Accept a natural language question about OS/software releases.
- Run the question through a chain of agents (router, vendor/date gate, retriever, fact builder, verifier, answer composer).
- Return either a verified version answer with evidence, or an explicit abstain response.

## Tech stack

- **FastAPI** for the HTTP API.
- **Gemini** for the Router (question classification); optional **OpenAI** for answer formatting.
- **httpx** for Releasetrain and the Node data layer.
- **Neo4j** – explainability graph: each query/answer is written as Query → Vendor → Release and Query → Evidence (optional; set `NEO4J_URI` to enable).

The data-lake layer (Postgres + Node.js, optional Redis cache) exposes `GET /facts/latest`, `GET /facts/on-date`, and `POST /ingest`. When `REDIS_HOST` is set (Render Key Value), fact lookups are cached for faster repeat queries.

### Hackathon sponsors we use

- **PostgreSQL (Render)** – Data lake store. All release/version facts are persisted in Postgres. The Node data layer uses `DATABASE_URL`.
- **Google Gemini** – Router agent (question type + vendor/date hints).
- **Neo4j** – Explainability graph (Query, Vendor, Release, Evidence nodes and relationships).
- **Airbyte** – Ingest path from Releasetrain into Postgres. See [docs/AIRBYTE_POSTGRES_INTEGRATION.md](docs/AIRBYTE_POSTGRES_INTEGRATION.md).

## Running locally

1. Create and activate a virtual environment (optional but recommended):

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set the required environment variables (at minimum):

- `OPENAI_API_KEY`
- `RELEASETRAIN_VENDOR_API` (default: `https://releasetrain.io/api/c/names`)
- `RELEASETRAIN_COMPONENT_API` (default: `https://releasetrain.io/api/component?q=os`)
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (if Neo4j is enabled)

You can store these in a `.env` file during development.

4. Run the development server:

```bash
uvicorn backend.main:app --reload
```

The health-check endpoint will be available at `GET /health`.

## Render deployment

On Render, configure a **Web Service**:

- Start command: `uvicorn backend.main:app --host 0.0.0.0 --port 10000`
- Environment: Python 3.11+ recommended.
- Add the same environment variables as above in the Render dashboard.

## High-level API

- `GET /health` – simple health check.
- `POST /answer` – main endpoint to run the agent pipeline.
- `GET /trace/{query_id}` – returns the internal agent trace for a past query (for the UI debug panel).

The detailed contract for `/answer` and `/trace` will be finalised once all agents are wired together.

---

## API keys and setup (full-fledged app)

### 1. API keys and env vars

| What | Required? | Where to get / set |
|------|-----------|--------------------|
| **GEMINI_API_KEY** | **Yes** (for Router) | [Google AI Studio](https://aistudio.google.com/apikey) → create key; set in `.env`. |
| **DATABASE_URL** | **Yes** (for Node data layer) | Postgres: [Render](https://render.com), [Neon](https://neon.tech), or local. Format: `postgresql://user:password@host:5432/dbname?sslmode=require` |
| **DATA_LAKE_SERVICE_URL** | For Python backend | Default `http://localhost:3000`. Set only if Node runs elsewhere. |
| REDIS_HOST / REDIS_PORT | Optional (cache) | e.g. Render Key Value; speeds up repeat fact lookups. |
| NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD | Optional | [Neo4j](https://neo4j.com) – explainability graph (Query → Vendor → Release, Evidence). |

Copy `.env.example` to `.env` and set at least `GEMINI_API_KEY` and `DATABASE_URL`. The Python backend reads `.env` when you run `uvicorn` from the repo root.

### 2. One-time setup

```bash
# Repo root
git clone <your-repo> && cd <repo>
cp .env.example .env   # then edit .env with your keys

# Node (data layer)
npm install

# Python (backend)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

### 3. Run the three services (order doesn’t matter for install, but Node must be up before you ask questions)

**Terminal 1 – Data layer (port 3000)**  
Needs `DATABASE_URL` in env or in `.env` (Node reads from process.env; you can `export $(cat .env | xargs)` or use a tool that loads `.env`).

```bash
export DATABASE_URL="postgresql://..."
npm run dev
```

**Terminal 2 – Python backend (port 8000)**  
Needs `GEMINI_API_KEY` and optionally `DATA_LAKE_SERVICE_URL` (default localhost:3000). Optional: `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`.

```bash
source .venv/bin/activate
export GEMINI_API_KEY="..."
# export DATA_LAKE_SERVICE_URL="http://localhost:3000"   # default
uvicorn backend.main:app --reload --port 8000
```

**Terminal 3 – Frontend (port 5173)**

```bash
cd frontend && npm run dev
```

Open **http://localhost:5173** and ask e.g. “What’s the latest version of Linux?”.  
If the data layer has no data yet, you’ll get “no record found” until you ingest (e.g. via Node’s `POST /ingest` or a one-off script that calls Releasetrain and then ingest).

---

## Full-stack run (Python backend + Node data layer + React frontend)

The app is integrated end-to-end: the **frontend** talks to the **Python backend**, which calls the **Node data layer** for facts.

### 1. Data layer (Far’s Node service) – port 3000

```bash
npm install
export DATABASE_URL="postgresql://..."   # required for Postgres
# optional: REDIS_HOST, REDIS_PORT for cache
npm run dev
```

Starts the Node server at `http://localhost:3000` with `GET /facts/latest`, `GET /facts/on-date`, `POST /ingest`, `POST /answer`.

### 2. Python backend (orchestrator + agents) – port 8000

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
export OPENAI_API_KEY="..."
export DATA_LAKE_SERVICE_URL="http://localhost:3000"   # Node service
uvicorn backend.main:app --reload --port 8000
```

Backend will call the Node service for facts and return answers + trace.

### 3. Frontend (Dar’s React UI) – port 5173

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/answer`, `/trace`, `/health` to `http://localhost:8000`. Open `http://localhost:5173`, ask a question, and see answer, evidence, and debug trace.

