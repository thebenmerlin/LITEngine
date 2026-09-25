---
title: LITEngine Backend
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: gradio
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

## Deploy to Hugging Face Spaces (Docker)

The Space repository is the contents of this `lit-backend/` directory. Its
`Dockerfile` and this README must appear at the root of the Space repository.
The image runs Python 3.11 as UID 1000, uses the CPU-only PyTorch wheel,
preloads the public MiniLM fallback model, and serves FastAPI on port 7860.
The included outcome artifact and precedent fixture index are committed to Git
and travel with the subtree.

1. Create a **Docker** Space named `litengine-backend` under your Hugging Face
   account. Choose CPU Basic hardware. Hugging Face currently requires a paid
   account plan to *create* a compute Space, even though CPU Basic has no hourly
   hardware charge. If this account cannot create one, this deployment target
   is unavailable until the account is eligible.
2. In the Space's **Settings → Variables and secrets**, set:

   | Name | Type | Value |
   |---|---|---|
   | `PORT` | Variable | `7860` |
   | `ENV` | Variable | `production` |
   | `ALLOWED_ORIGINS` | Variable | Exact frontend origin(s), comma-separated, for example `https://litengine.example.com` |
   | `HUGGINGFACE_API_KEY` | Secret | An Inference API token, if using the hosted embedding path |

   `HUGGINGFACE_API_KEY` is optional if using the local MiniLM fallback. The
   GitHub deployment token `HF_TOKEN` is separate and must never be put in
   Space variables or committed to Git.
3. After the backend changes are committed on the monorepo's `main` branch,
   set `HF_USER` to the Space owner and run from the monorepo root:

   ```bash
   HF_USER=your-hf-username
   git remote add hf "https://huggingface.co/spaces/${HF_USER}/litengine-backend"
   git fetch hf main
   git log --oneline -3 hf/main  # inspect the new Space's starter commit
   split_sha=$(git subtree split --prefix=lit-backend HEAD)
   git push --force-with-lease=refs/heads/main:$(git rev-parse hf/main) hf "$split_sha:refs/heads/main"
   ```

   The initial push replaces the **new, dedicated Space's starter README**
   with the backend subtree. Use it only after reviewing `hf/main`; it does
   not overwrite a Space with work you want to keep. Git prompts for your
   Hugging Face username and a write-scoped access token as the password.
   Subsequent pushes are fast-forward and need no force:

   ```bash
   git push hf "$(git subtree split --prefix=lit-backend HEAD):refs/heads/main"
   ```

4. For automatic pushes from GitHub `main`, set the repository **variable**
   `HF_USER` to the Space owner and **secret** `HF_TOKEN` to a fine-grained
   token with write access to only this Space. The
   monorepo's `.github/workflows/deploy-hf-space.yml` pushes the subtree when
   `lit-backend/` changes; it requires the initial seed above.
5. Set the GitHub repository **variable** `HF_SPACE_URL` to the public direct
   URL, usually `https://your-hf-username-litengine-backend.hf.space` (use the exact
   URL shown by your Space). The
   monorepo's `.github/workflows/keep-alive.yml` calls `/health` every six hours
   and supports a manual run from the Actions tab. It fails
   visibly if the request or JSON health check fails. Scheduled GitHub Actions
   may be delayed and can be disabled after 60 days without activity in a
   public repository, so this is best effort rather than an uptime guarantee.

Verify once the Space reports **Running**:

```bash
HF_SPACE_URL=https://your-hf-username-litengine-backend.hf.space
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
