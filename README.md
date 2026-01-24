# JobForge AI - Intelligent Job Application Agent

An intelligent job application agent that helps you find, score, and apply to the right jobs with human-in-the-loop safety.

## Features

- **Resume Analysis**: Upload and analyze your resume to identify role matches
- **Smart Job Ingestion**: Pull jobs from LinkedIn, Workday, Glassdoor, and company portals
- **Intelligent Scoring**: Multi-factor scoring (0-100) with explainable breakdowns
- **Artifact Generation**: Generate tailored resumes, recruiter pitches, and screening answers
- **Assisted Apply**: Browser automation that stops before final submit (human gate)
- **Outcome Tracking**: Track application outcomes and improve scoring over time

## Architecture

- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: React + TypeScript (Next.js)
- **Database**: PostgreSQL with pgvector
- **Cache & Queue**: Redis
- **LLM**: OpenAI API (GPT-4 for parsing, GPT-3.5 for scoring)

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 16+ with pgvector extension
- Redis 7+
- Node.js 18+ (for frontend)
- OpenAI API key

### Setup

1. **Clone and install dependencies**:
```bash
pip install -e .
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Start services with Docker Compose**:
```bash
cd infra
docker-compose up -d
```

4. **Run database migrations**:
```bash
alembic -c packages/database/alembic.ini upgrade head
```

5. **Start the API**:
```bash
cd apps/web
uvicorn main:app --reload
```

6. **Start Celery worker** (in separate terminal):
```bash
cd apps/worker
celery -A celery_app worker --loglevel=info
```

7. **Start frontend** (in separate terminal):
```bash
cd apps/web/frontend
npm install
npm run dev
```

## API Endpoints

### Resume
- `POST /api/v1/resume/upload` - Upload resume
- `POST /api/v1/resume/analyze/{resume_id}` - Analyze resume
- `GET /api/v1/resume/roles/{resume_id}` - Get suggested roles

### Preferences
- `GET /api/v1/preferences` - Get user preferences
- `POST /api/v1/preferences` - Create preferences
- `PUT /api/v1/preferences` - Update preferences

### Jobs
- `POST /api/v1/jobs/ingest` - Ingest a job
- `POST /api/v1/jobs/ingest/linkedin` - Scrape from LinkedIn
- `POST /api/v1/jobs/{job_id}/parse` - Parse job description
- `POST /api/v1/jobs/{job_id}/score` - Score job fit
- `GET /api/v1/jobs/{job_id}/decision` - Get decision

### Artifacts
- `POST /api/v1/jobs/{job_id}/artifacts/generate` - Generate artifacts
- `GET /api/v1/jobs/{job_id}/artifacts` - List artifacts

### Apply
- `POST /api/v1/jobs/{job_id}/apply/assisted/start` - Start assisted apply
- `POST /api/v1/jobs/{job_id}/apply/submit` - Submit application

## Project Structure

```
jobforge-ai/
├── apps/
│   ├── web/              # FastAPI backend + React frontend
│   └── worker/           # Celery worker for background tasks
├── services/
│   ├── resume_analyzer/  # Resume parsing & role extraction
│   ├── job_ingestion/    # Multi-source job scraping
│   ├── jd_parser/        # JD parsing agent
│   ├── scoring/          # Fit scoring service
│   ├── decision_engine/  # Apply/validate/skip logic
│   ├── artifacts/        # Resume tailoring & generation
│   └── apply_bot/        # Browser automation
├── packages/
│   ├── schemas/          # Pydantic models
│   ├── database/         # SQLAlchemy models & migrations
│   └── common/           # Shared utilities (Redis, logging)
└── config/               # Configuration files
```

## Risk Mitigation

See [docs/risk_mitigation_strategy.md](docs/risk_mitigation_strategy.md) for comprehensive risk mitigation strategies.

Key mitigations:
- **Redis caching** for LLM responses (60%+ cost reduction)
- **Rate limiting** for all scraping operations
- **Human-in-the-loop** for all application submissions
- **Schema validation** with repair logic and fallback parsers
- **Comprehensive error handling** and graceful degradation

## Development

### Running Tests

```bash
pytest tests/
```

### Code Quality

```bash
black .
ruff check .
mypy .
```

## License

MIT
