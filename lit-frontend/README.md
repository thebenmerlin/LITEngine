# Legal Intelligence Terminal (LIT) — Frontend

Vite + React frontend for the Legal Intelligence Terminal — an AI-powered legal research platform for Indian courts. Provides semantic precedent search, automated fact extraction, argument graph visualization, judicial outcome simulation, and a what-if analyzer.

---

## Screenshots

| Feature | Preview |
|---|---|
| Home Dashboard | _[Screenshot placeholder]_ |
| Precedent Search | _[Screenshot placeholder]_ |
| Fact Extraction | _[Screenshot placeholder]_ |
| Argument Graph | _[Screenshot placeholder]_ |
| Judicial Simulation | _[Screenshot placeholder]_ |
| What-If Analyzer | _[Screenshot placeholder]_ |

---

## Features

- **Precedent Search** — Semantic search across Indian case law with FAISS-powered vector similarity and live Kanoon fallback
- **Fact Extraction** — Automatically extract parties, sections, acts, and key facts from raw judgment text using InLegalBERT
- **Argument Graph** — Visualize legal argument structure as an interactive Cytoscape.js force-directed graph with weak-node detection
- **Judicial Simulation** — Predict case outcomes with explainable scoring based on precedent alignment, statutory strength, and argument completeness
- **What-If Analyzer** — Modify case parameters in real-time and instantly see how outcome probability shifts — no API calls needed

---

## Local Development Setup

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd lit-frontend

# 2. Install dependencies
npm install

# 3. Configure environment (auto-loaded for dev)
# .env.development is already set to http://localhost:8000/api/v1
# Make sure the backend is running on port 8000

# 4. Start the dev server
npm run dev
# → http://localhost:3000
```

The dev server proxies `/api/*` requests to the backend, so CORS is not needed locally.

---

## Deploy on Vercel

1. **Connect your repo** — Push this `lit-frontend/` directory to GitHub and connect it to a new Vercel project.

2. **Configure environment variables** (Settings → Environment Variables):

   | Variable | Value |
   |---|---|
   | `VITE_API_BASE_URL` | `https://your-lit-backend.onrender.com/api/v1` |

3. **Build settings** — Vercel auto-detects Vite. No custom build command needed.

4. **Deploy** — Push to the connected branch and Vercel will build and deploy automatically.

   > `vercel.json` is included with SPA rewrites (for React Router) and security headers.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Backend API base URL |

The `.env.development` and `.env.production` files provide defaults for each environment. Override on Vercel via the dashboard.

---

## Project Structure

```
src/
├── components/
│   ├── layout/          # Sidebar, Topbar, Layout wrapper
│   └── ui/              # Reusable UI: Button, Card, Badge, Spinner, …
├── pages/               # Route pages: Home, PrecedentSearch, …
├── context/             # ThemeContext (dark mode)
├── hooks/               # useTheme, useSettings, useApi
├── lib/                 # API client (fetch-based, zero dependencies)
├── utils/               # whatIfCalculator (client-side heuristic)
└── styles/              # Tailwind globals
```

---

## Tech Stack

- **Vite 6** — Build tool and dev server
- **React 18** — UI framework
- **React Router v6** — Client-side routing
- **Tailwind CSS v3** — Utility-first styling with dark mode
- **Cytoscape.js** — Argument graph visualization
- **Lucide React** — Icon library

Zero extra dependencies beyond what's in `package.json`.
