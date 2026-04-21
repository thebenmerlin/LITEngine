# Legal Intelligence Terminal (LIT)

[![Backend: FastAPI](https://img.shields.io/badge/backend-fastapi-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Frontend: React + Vite](https://img.shields.io/badge/frontend-react+ vite-61dafb?style=flat&logo=react)](https://react.dev/)
[![Python: 3.11](https://img.shields.io/badge/python-3.11-3776ab?style=flat&logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**AI-powered legal intelligence system for Indian courts.** LIT combines semantic search, automated fact extraction, argument graph visualization, and judicial outcome prediction to transform legal research and case analysis.

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture Overview](#-architecture-overview)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Backend Documentation](#-backend-documentation)
- [Frontend Documentation](#-frontend-documentation)
- [Deployment](#-deployment)
- [API Reference](#-api-reference)
- [Development Guidelines](#-development-guidelines)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

### 🔍 Semantic Precedent Search
- FAISS-powered vector similarity search across Indian case law
- Live fallback to Indian Kanoon for real-time judgment retrieval
- Embedding models via Hugging Face Inference API or local SentenceTransformers

### 📄 Automated Fact Extraction
- Extract structured case profiles from raw judgment text
- Identify parties, sections, acts, dates, and key factual elements
- Powered by InLegalBERT and custom NLP pipelines
- Batch processing support with async task tracking

### 🕸️ Argument Graph Construction
- Visualize legal argument structure as interactive knowledge graphs
- Detect weak nodes and logical gaps in argumentation
- Built with Cytoscape.js force-directed layouts

### ⚖️ Judicial Outcome Simulation
- Predict case outcomes with explainable scoring
- Analyze precedent alignment, statutory strength, and argument completeness
- Real-time what-if scenario testing (client-side)

### 🎨 Modern User Experience
- Dark mode support with Tailwind CSS
- Responsive design for desktop and mobile
- Interactive visualizations and real-time feedback

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         LIT Platform                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐         ┌─────────────────────────────┐  │
│  │   Frontend       │         │        Backend              │  │
│  │   (Vite+React)   │◄───────►│       (FastAPI)             │  │
│  │   Port: 3000     │  REST   │       Port: 8000            │  │
│  └──────────────────┘  API    └─────────────────────────────┘  │
│         │                                    │                  │
│         │                                    ▼                  │
│         │                    ┌───────────────────────────────┐ │
│         │                    │        Services Layer         │ │
│         │                    │  • Embedder (FAISS + HF)      │ │
│         │                    │  • Kanoon Scraper             │ │
│         │                    │  • Fact Extractor             │ │
│         │                    │  • Graph Builder              │ │
│         │                    │  • Outcome Simulator          │ │
│         │                    └───────────────────────────────┘ │
│         │                                    │                  │
│         ▼                                    ▼                  │
│  ┌──────────────────┐         ┌─────────────────────────────┐  │
│  │  External APIs   │         │      Data Sources           │  │
│  │  • Hugging Face  │         │  • Indian Kanoon            │  │
│  │  • Inference API │         │  • Local Fixtures (dev)     │  │
│  └──────────────────┘         └─────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** ([download](https://www.python.org/downloads/))
- **Node.js 18+** ([download](https://nodejs.org/))
- **Git** ([download](https://git-scm.com/))
- **Hugging Face API Key** (free at [huggingface.co](https://huggingface.co/settings/tokens))

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/lit.git
cd lit
```

### 2. Backend Setup

```bash
cd lit-backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set your HUGGINGFACE_API_KEY

# Optional: Use fixtures for offline development
export USE_FIXTURES=true

# Start the server
uvicorn main:app --reload
```

✅ Backend running at: **http://localhost:8000**  
📚 Swagger docs: **http://localhost:8000/docs**

### 3. Frontend Setup

```bash
# Open a new terminal
cd lit-frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

✅ Frontend running at: **http://localhost:3000**

---

## 📁 Project Structure

```
lit/
├── lit-backend/                 # FastAPI backend
│   ├── routers/                 # API route handlers
│   │   ├── precedent.py         # Precedent search endpoints
│   │   ├── facts.py             # Fact extraction endpoints
│   │   ├── graph.py             # Argument graph endpoints
│   │   └── simulation.py        # Outcome prediction endpoints
│   ├── services/                # Business logic layer
│   │   ├── embedder.py          # Vector embeddings & FAISS
│   │   ├── kanoon.py            # Indian Kanoon scraper
│   │   ├── extractor.py         # NLP fact extraction
│   │   ├── graph_builder.py     # Knowledge graph construction
│   │   └── simulator.py         # Outcome prediction engine
│   ├── models/                  # Pydantic schemas
│   ├── utils/                   # Utilities (logger, cache, etc.)
│   ├── fixtures/                # Sample data for offline dev
│   ├── config.py                # Configuration management
│   ├── main.py                  # Application entry point
│   ├── requirements.txt         # Python dependencies
│   ├── render.yaml              # Render deployment config
│   └── .env.example             # Environment template
│
├── lit-frontend/                # Vite + React frontend
│   ├── src/
│   │   ├── components/          # Reusable UI components
│   │   │   ├── layout/          # Sidebar, Topbar, Layout
│   │   │   └── ui/              # Button, Card, Badge, etc.
│   │   ├── pages/               # Route pages
│   │   ├── context/             # React context providers
│   │   ├── hooks/               # Custom React hooks
│   │   ├── lib/                 # API client
│   │   ├── utils/               # Helper functions
│   │   └── styles/              # Global styles
│   ├── public/                  # Static assets
│   ├── package.json             # Node dependencies
│   ├── vite.config.js           # Vite configuration
│   ├── tailwind.config.js       # Tailwind CSS config
│   ├── vercel.json              # Vercel deployment config
│   └── .env.example             # Environment template
│
├── runtime.txt                  # Python runtime version
└── README.md                    # This file
```

---

## 📚 Backend Documentation

See [`lit-backend/README.md`](lit-backend/README.md) for detailed documentation including:

- Complete API endpoint reference
- Environment variable configuration
- Render deployment guide
- Cold start optimization tips

### Key Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | FastAPI 0.111 | High-performance async API |
| Validation | Pydantic 2.7 | Data validation & serialization |
| Embeddings | SentenceTransformers / HF API | Vector representations |
| Vector Store | FAISS 1.13 | Similarity search index |
| Scraping | BeautifulSoup4 + httpx | Web scraping & HTTP client |
| Logging | Loguru | Structured logging |

### Core Services

#### Embedder Service
- Manages FAISS index for precedent vectors
- Supports both local model inference and Hugging Face API
- Automatic index persistence and reloading

#### Kanoon Service
- Scrapes Indian Kanoon for live judgments
- Respects robots.txt and rate limits
- Falls back to fixtures in development

#### Extractor Service
- Uses InLegalBERT for legal NLP tasks
- Extracts parties, sections, acts, facts
- Async batch processing with task tracking

#### Graph Builder
- Constructs argument graphs from case profiles
- Identifies weak nodes and logical gaps
- Exports to Cytoscape.js format

#### Simulator Service
- Predicts judicial outcomes
- Explainable scoring breakdown
- Heuristic-based reasoning

---

## 💻 Frontend Documentation

See [`lit-frontend/README.md`](lit-frontend/README.md) for detailed documentation including:

- Feature screenshots
- Component architecture
- Vercel deployment guide
- Development workflow

### Key Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| Build Tool | Vite 6 | Fast builds & HMR |
| Framework | React 18 | UI component library |
| Routing | React Router v6 | Client-side navigation |
| Styling | Tailwind CSS v3 | Utility-first CSS |
| Visualization | Cytoscape.js | Graph rendering |
| Icons | Lucide React | Icon library |

### Pages

| Page | Route | Description |
|------|-------|-------------|
| Dashboard | `/` | System overview & quick actions |
| Precedent Search | `/precedents` | Semantic search interface |
| Fact Extraction | `/facts` | Document upload & extraction |
| Argument Graph | `/graph` | Interactive graph visualization |
| Simulation | `/simulation` | Outcome prediction tool |

---

## 🌐 Deployment

### Backend on Render (Free Tier)

1. **Create Web Service** on Render and connect your repository
2. **Configure:**
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Health Check:** `/api/v1/health/ready`

3. **Set Environment Variables:**

   | Variable | Value |
   |----------|-------|
   | `HUGGINGFACE_API_KEY` | `hf_your_key` |
   | `KANOON_BASE_URL` | `https://indiankanoon.org` |
   | `ALLOWED_ORIGINS` | `https://your-frontend.vercel.app` |
   | `USE_FIXTURES` | `false` |
   | `ENV` | `production` |
   | `PORT` | `10000` |

4. **Deploy** — The `render.yaml` file provides automatic configuration

> ⚠️ **Cold Start Warning:** Free tier instances spin down after 15 minutes of inactivity. First request may take 30–60 seconds while the embedding model loads.

### Frontend on Vercel

1. **Connect Repository** to Vercel
2. **Set Environment Variable:**
   - `VITE_API_BASE_URL` = `https://your-backend.onrender.com/api/v1`
3. **Deploy** — Vercel auto-detects Vite configuration

The `vercel.json` includes SPA rewrites for React Router and security headers.

### Environment-Specific Configurations

| Environment | Backend URL | Frontend URL | Notes |
|-------------|-------------|--------------|-------|
| Development | `http://localhost:8000` | `http://localhost:3000` | Uses fixtures, relaxed CORS |
| Production | Render web service | Vercel deployment | Live Kanoon scraping, strict CORS |

---

## 📡 API Reference

### Health Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Basic health check |
| `GET` | `/api/v1/health/ready` | Readiness probe (for load balancers) |

### Precedent Module

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/precedent/` | Module status |
| `POST` | `/api/v1/precedent/search` | Semantic search |
| `GET` | `/api/v1/precedent/{doc_id}` | Fetch judgment detail |
| `POST` | `/api/v1/precedent/index` | Index document |
| `GET` | `/api/v1/precedent/index/stats` | Index statistics |

### Facts Module

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/facts/` | Module status |
| `POST` | `/api/v1/facts/extract` | Extract facts from text |
| `POST` | `/api/v1/facts/extract/batch` | Batch extraction (up to 5) |
| `GET` | `/api/v1/facts/status/{task_id}` | Poll async task |

### Graph Module

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/graph/` | Module status |
| `POST` | `/api/v1/graph/build` | Build argument graph |
| `POST` | `/api/v1/graph/query` | Query knowledge graph |

### Simulation Module

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/simulation/` | Module status |
| `POST` | `/api/v1/simulation/predict` | Predict outcome |

Full interactive API documentation is available at `/docs` when running the backend.

---

## 🛠️ Development Guidelines

### Code Style

**Backend (Python):**
- Follow PEP 8 style guidelines
- Use type hints for all function signatures
- Docstrings for public methods (Google style)
- Maximum line length: 88 characters

**Frontend (JavaScript/React):**
- ESLint configuration provided in `eslint.config.js`
- Use functional components with hooks
- PropTypes or TypeScript for component props
- Consistent naming: PascalCase for components, camelCase for variables

### Testing

```bash
# Backend tests (when available)
cd lit-backend
pytest

# Frontend tests (when available)
cd lit-frontend
npm test
```

### Git Workflow

1. Create feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -m "feat: description"`
3. Push branch: `git push origin feature/your-feature`
4. Open Pull Request

Commit message format:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `style:` Formatting
- `refactor:` Code restructuring
- `test:` Adding tests
- `chore:` Maintenance

### Security Best Practices

- Never commit `.env` files or API keys
- Rotate Hugging Face tokens periodically
- Validate all user inputs (handled by Pydantic)
- Use HTTPS in production
- Enable CORS only for trusted origins

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'feat: add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Areas for Contribution

- [ ] Additional legal NLP models
- [ ] Support for more Indian court databases
- [ ] Enhanced visualization features
- [ ] Unit and integration tests
- [ ] Documentation improvements
- [ ] Performance optimizations

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Indian Kanoon** - Free legal resource for Indian case law
- **Hugging Face** - Open-source AI models and Inference API
- **FAISS** - Facebook AI Similarity Search library
- **InLegalBERT** - Legal domain BERT model

---

## 📞 Support

- **Documentation:** See individual README files in `lit-backend/` and `lit-frontend/`
- **Issues:** Report bugs via GitHub Issues
- **API Docs:** Access `/docs` endpoint on running backend

---

<div align="center">

**Built with ❤️ for the Indian legal community**

[⬆ Back to Top](#legal-intelligence-terminal-lit)

</div>
