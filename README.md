# JobForge AI

> Career infra tool: score-first, apply-second, human-in-the-loop safety.

---

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI (Python 3.11+) |
| DB | PostgreSQL + pgvector |
| Cache | Redis |
| LLM | Azure OpenAI (GPT-4.1) |
| Storage | Azure Blob Storage |
| Frontend | React 18 + Vite + TailwindCSS |
| Dependency mgmt | Poetry (Python) · npm (Node) |

---

## Setup

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)
- Node.js 20+ (use `.nvmrc`: `nvm use` in `apps/web-ui/`)
- Docker (for PostgreSQL + Redis)
- Azure OpenAI + Blob Storage credentials

### 1. Clone and install all dependencies

```bash
git clone https://github.com/vijayreddybathula/jobforge-ai
cd jobforge-ai

# Install everything (Python + Node)
make install

# Or separately:
poetry install          # Python deps (includes bcrypt, fastapi, sqlalchemy, etc.)
cd apps/web-ui && npm install   # Frontend deps
```

### 2. Environment variables

Copy `.env.example` and fill in your credentials:

```bash
cp .env.example .env
```

Required variables:

```
AZURE_BLOB_CONNECTION_STRING=...
AZURE_OPENAPI_KEY=...
AZURE_OPENAPI_ENDPOINT=...
AZURE_OPENAPI_DEPLOYMENT=gpt-4.1
AZURE_OPENAPI_VERSION=2024-06-01-preview
JSEARCH_API_KEY=...
JSEARCH_API_HOST=jsearch.p.rapidapi.com
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jobforge_ai
REDIS_URL=redis://localhost:6379
```

### 3. Start infrastructure

```bash
docker-compose up -d   # starts PostgreSQL + Redis
```

### 4. Run database migrations

```bash
poetry run alembic upgrade head
```

### 5. Start the API

```bash
make dev-api
# FastAPI running at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### 6. Start the frontend

```bash
make dev-ui
# Vite running at http://localhost:5173
# Proxies /api/* to http://localhost:8000
```

---

## Python dependencies

All managed by **Poetry** via `pyproject.toml`. No `pip install` needed.

Key packages:
- `bcrypt >=4.0.0` — password hashing for login
- `passlib[bcrypt] >=1.7.4` — password utilities
- `fastapi` — API framework
- `sqlalchemy` — ORM
- `azure-storage-blob` — resume file storage
- `openai` — Azure OpenAI client

To add a new Python package:
```bash
poetry add <package-name>
```

---

## Node dependencies

All managed by **npm** via `apps/web-ui/package.json`.

Key packages:
- `react` + `react-dom` — UI framework
- `react-router-dom` — SPA routing
- `tailwindcss` — styling
- `lucide-react` — icons
- `react-dropzone` — file upload UX

To add a new frontend package:
```bash
cd apps/web-ui && npm install <package-name>
```

---

## Architecture

See [`docs/DATA_ISOLATION.md`](docs/DATA_ISOLATION.md) for the full multi-user security model.

See [`docs/FRONTEND_UX_ARCHITECTURE.md`](docs/FRONTEND_UX_ARCHITECTURE.md) for screen designs and sprint plan.

---

## Pipeline

```
Upload Resume → Analyze (LLM) → Confirm Roles → Build Profile
       ↓
Search Jobs (JSearch API) → Parse JDs (LLM) → Score (Rules + LLM)
       ↓
Generate Artifacts (pitch + bullets + answers) → Assisted Apply
       ↓
Record Outcomes → Feedback Loop → Score Calibration
```

---

## Branch strategy

- **Never push to `main` directly.**
- All work in feature branches → PR → merge.
- Active branch: `feature/jsearch-job-ingestion`
