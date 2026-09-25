---
title: LITEngine Backend
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: gradio
python_version: 3.12.12
sdk_version: 4.44.0
app_file: app.py
pinned: false
---

# Legal Intelligence Terminal (LIT) — Backend

AI-powered legal intelligence system for Indian courts. This FastAPI backend provides semantic precedent search, automated fact extraction from case text, argument graph construction, and judicial outcome simulation. It integrates with Indian Kanoon for live judgment scraping and uses Hugging Face's Inference API for embeddings and legal NLP.

---

## Local Setup

```bash
# 1. Clone the repo and enter the backend directory
git clone <your-repo-url>
cd lit-backend

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — set HUGGINGFACE_API_KEY and other values as needed

# 5. (Optional) Use fixtures for offline development
export USE_FIXTURES=true

# 6. Start the server
uvicorn main:app --reload
# → http://localhost:8000
# → Swagger docs: http://localhost:8000/docs
```

---

## Deploy to Hugging Face Spaces (Gradio on ZeroGPU)

The Space repository is the contents of this `lit-backend/` directory. This
README and `app.py` must appear at its root. The Gradio entrypoint mounts the
existing FastAPI app, including `/health`, `/docs`, and `/api/v1/...`, on port
7860. ZeroGPU currently supports Python 3.10.13 and 3.12.12; this Space pins
3.12.12 because its trained outcome model needs scikit-learn 1.8.0, which
requires Python 3.11 or newer. Keep that dependency and the committed model
artifact together when deploying.

1. Use the existing **Gradio** Space `thebenmerlin/lit-backend` on **ZeroGPU**.
   Free personal accounts in good standing may host up to two ZeroGPU Spaces.
2. In the Space's **Settings → Variables and secrets**, set:

   | Name | Type | Value |
   |---|---|---|
   | `ENV` | Variable | `production` |
   | `ALLOWED_ORIGINS` | Variable | Exact frontend origin(s), comma-separated, for example `https://litengine.example.com` |
   | `HUGGINGFACE_API_KEY` | Secret | An Inference API token, if using the hosted embedding path |

   `HUGGINGFACE_API_KEY` is optional if using the local MiniLM fallback. The
   GitHub deployment token `HF_TOKEN` is separate and must never be put in
   Space variables or committed to Git.
3. Commit backend changes to the monorepo's `main` branch. The monorepo's
   `.github/workflows/deploy-hf.yml` deploys only the `lit-backend/` subtree to
   the Space. Set the GitHub repository **secret** `HF_TOKEN` to a fine-grained
   token with write access to this Space.
4. Set the GitHub repository **variable** `HF_SPACE_URL` to the public direct
   URL, `https://thebenmerlin-lit-backend.hf.space`. The
   monorepo's `.github/workflows/keep-alive.yml` calls `/health` every six hours
   and supports a manual run from the Actions tab. It fails
   visibly if the request or JSON health check fails. Scheduled GitHub Actions
   may be delayed and can be disabled after 60 days without activity in a
   public repository, so this is best effort rather than an uptime guarantee.

Verify once the Space reports **Running**:

```bash
HF_SPACE_URL=https://thebenmerlin-lit-backend.hf.space
curl --fail-with-body --show-error --max-time 30 \
  "${HF_SPACE_URL}/health"
# Expect JSON containing "status":"healthy".
curl --fail-with-body --show-error --max-time 30 \
  "${HF_SPACE_URL}/api/v1/health/ready"
# Check outcome_model_loaded and index_loaded before testing model endpoints.
```

Then manually run both GitHub workflows and check their logs. If the frontend
is deployed separately, point its backend URL to the same direct Space URL and
check CORS from that exact frontend origin. `logs/`, `fixtures/`, and `data/`
are writable but Space-local runtime changes are ephemeral; persist any new
data outside the Space before relying on it.

---

## Deploy on Render (Free Tier)

For private Oracle A1 VM staging, see [deploy/oracle/README.md](deploy/oracle/README.md).

1. **Connect your repo** — On Render, create a new **Web Service** and connect the Git repository containing this `lit-backend/` directory.

2. **Configure the service:**
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path:** `/api/v1/health/ready`

3. **Set environment variables** (Dashboard → Environment):

   | Key | Value |
   |---|---|
   | `HUGGINGFACE_API_KEY` | `hf_your_real_key` |
   | `KANOON_BASE_URL` | `https://indiankanoon.org` |
   | `ALLOWED_ORIGINS` | `https://your-frontend.vercel.app` |
   | `USE_FIXTURES` | `false` |
   | `ENV` | `production` |

4. **Deploy** — Click Deploy. Render will use `render.yaml` for automatic configuration.

   > The `Procfile` and `runtime.txt` are provided as fallbacks if `render.yaml` is not detected.

---

## API Endpoints

### Health

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Basic health check — returns app name, version, status |
| GET | `/api/v1/health/ready` | Readiness probe for Render — returns `ready`, `index_loaded`, `hf_key_set` |

### Precedent Search

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/precedent/` | Module status check |
| POST | `/api/v1/precedent/search` | Semantic search over precedents (FAISS + Kanoon fallback) |
| GET | `/api/v1/precedent/{doc_id}` | Fetch full judgment detail from Kanoon |
| POST | `/api/v1/precedent/index` | Index a document into the FAISS index |
| GET | `/api/v1/precedent/index/stats` | FAISS index statistics |

### Fact Extraction

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/facts/` | Module status check |
| POST | `/api/v1/facts/extract` | Extract structured case profile from raw text |
| POST | `/api/v1/facts/extract/batch` | Batch extract up to 5 cases concurrently |
| GET | `/api/v1/facts/status/{task_id}` | Poll async extraction task status |

### Argument Graph

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/graph/` | Module status check |
| POST | `/api/v1/graph/build` | Build argument graph from a StructuredCaseProfile |
| POST | `/api/v1/graph/query` | Query the knowledge graph |

### Judicial Simulation

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/simulation/` | Module status check |
| POST | `/api/v1/simulation/predict` | Predict judicial outcome with explainable scoring |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `HUGGINGFACE_API_KEY` | *(empty)* | HF Inference API token for embeddings |
| `KANOON_BASE_URL` | `https://api.kanoon.example.com/v1` | Base URL for Indian Kanoon scraper |
| `ALLOWED_ORIGINS` | `*` | Comma-separated list of allowed CORS origins |
| `PORT` | `8000` | Server port |
| `ENV` | `development` | `development` or `production` — controls CORS strictness |
| `USE_FIXTURES` | `false` | Use local fixture data instead of live scraping |
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `CACHE_TTL` | `3600` | In-memory cache TTL in seconds |

---

## Cold Start Warning (Render Free Tier)

Render's free tier spins down instances after **15 minutes of inactivity**. On the first request after a cold start:

- The local SentenceTransformer embedding model (used as fallback when no valid HF API key is set) must be downloaded and loaded from the Hugging Face Hub.
- This initial load may take **30–60 seconds**.
- Subsequent requests are fast — the model stays cached in memory until the instance is spun down again.
- If you provide a valid `HUGGINGFACE_API_KEY`, embeddings are computed via the HF Inference API and there is no local model load, but the HF API itself may return a 503 while the model is warming up on their side (handled automatically with retry logic).

For production use, consider upgrading to a paid Render tier or pre-warming the instance.
