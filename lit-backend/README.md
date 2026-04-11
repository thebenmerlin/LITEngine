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

## Deploy on Render (Free Tier)

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
