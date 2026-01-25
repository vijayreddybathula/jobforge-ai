# JobForge AI - Local Setup & Execution Guide

Complete guide for setting up and running JobForge AI locally on macOS.

## 📋 Table of Contents
1. [System Requirements](#system-requirements)
2. [Installation & Setup](#installation--setup)
3. [Configuration](#configuration)
4. [Running the Application](#running-the-application)
5. [Common Commands](#common-commands)
6. [Troubleshooting](#troubleshooting)
7. [API Documentation](#api-documentation)

---

## 🖥️ System Requirements

### Prerequisites
- **macOS** (Apple Silicon or Intel)
- **Python 3.13** (system-wide)
- **Rancher Desktop** or Docker Desktop (for container runtime)
- **Homebrew** (for package management)
- **OpenAI API Key** (for LLM features)

### Optional
- **Node.js 18+** (for frontend development)
- **Git** (for version control)

---

## 📦 Installation & Setup

### 1. Install Global Dependencies

```bash
# Install Poetry (Python package manager)
curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Verify Poetry installation
poetry --version
# Expected: Poetry (version 2.3.1+)
```

### 2. Start Rancher Desktop

```bash
# Launch Rancher Desktop (UI or command line)
open -a "Rancher Desktop"

# Or if installed via CLI
rancher-desktop

# Configure Docker socket for local access
export DOCKER_HOST=unix://$HOME/.rd/docker.sock
```

### 3. Clone & Navigate to Project

```bash
cd /Users/vijayreddy/work_project/jobforge-ai
```

### 4. Create Poetry Virtual Environment

```bash
# Install all dependencies (automatically creates venv)
poetry install --no-root

# Verify environment
poetry env info
# Should show Python 3.13.8 and valid environment
```

### 5. Install & Activate Environment

```bash
# Option 1: Use Poetry shell (recommended for this session)
poetry shell

# Option 2: Use eval for one-time activation
eval $(poetry env activate)

# Option 3: Create alias for quick access
alias activate-jobforge="source /Users/vijayreddy/Library/Caches/pypoetry/virtualenvs/jobforge-ai-rtoSKEtt-py3.13/bin/activate"
activate-jobforge
```

---

## ⚙️ Configuration

### 1. Environment Variables

Create/update `.env` file in project root:

```bash
# PostgreSQL Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=jobforge_password
POSTGRES_DB=jobforge_ai

# Redis Configuration
REDIS_PASSWORD=redis_password
REDIS_HOST=localhost
REDIS_PORT=6379

# Database URLs
DATABASE_URL=postgresql://postgres:jobforge_password@localhost:5432/jobforge_ai
CELERY_BROKER_URL=redis://:redis_password@localhost:6379/1
CELERY_RESULT_BACKEND=redis://:redis_password@localhost:6379/2

# OpenAI Configuration (REQUIRED)
OPENAI_API_KEY=sk-proj-your-actual-key-here
OPENAI_ORG_ID=
OPENAI_MODEL_PARSING=gpt-4
OPENAI_MODEL_SCORING=gpt-3.5-turbo

# Application Configuration
ENV=development
DEBUG=true
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000

# Optional: LinkedIn/Job Site Credentials
LINKEDIN_USERNAME=
LINKEDIN_PASSWORD=
WORKDAY_USERNAME=
WORKDAY_PASSWORD=
```

### 2. Get OpenAI API Key

1. Visit: https://platform.openai.com/api-keys
2. Create a new secret key
3. Copy the key (starts with `sk-proj-`)
4. Update `OPENAI_API_KEY` in `.env`

### 3. Load Environment Variables

```bash
# Option 1: Source before running (one-time)
source .env

# Option 2: Use dotenv (automatic in Python apps)
# The app uses `load_dotenv()` to load .env automatically
```

---

## 🚀 Running the Application

### Option A: Full Docker Setup (Recommended)

#### 1. Start All Services (PostgreSQL, Redis, FastAPI, Celery)

```bash
# Set Docker socket
export DOCKER_HOST=unix://$HOME/.rd/docker.sock

# Navigate to infra folder
cd /Users/vijayreddy/work_project/jobforge-ai/infra

# Start all containers
docker-compose up -d

# Verify all services are running
docker-compose ps
```

#### Expected Output:
```
NAME                IMAGE                    COMMAND                  STATUS
jobforge-postgres   pgvector/pgvector:pg16   docker-entrypoint.s...   Up (healthy)
jobforge-redis      redis:latest             docker-entrypoint.s...   Up (healthy)
jobforge-web        infra-web                uvicorn apps.web.ma...   Up
jobforge-worker     infra-worker             celery -A apps.work...   Up
```

#### 2. Check Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web      # FastAPI logs
docker-compose logs -f worker   # Celery worker logs
docker-compose logs -f postgres # PostgreSQL logs
```

#### 3. Stop All Services

```bash
docker-compose down

# Remove volumes (clears data)
docker-compose down -v
```

---

### Option B: Hybrid Setup (Terminal + Docker)

Useful for development with hot-reload.

#### 1. Start Database Services Only

```bash
export DOCKER_HOST=unix://$HOME/.rd/docker.sock
cd /Users/vijayreddy/work_project/jobforge-ai/infra

# Start only PostgreSQL and Redis
docker-compose up -d postgres redis
```

#### 2. Run Database Migrations

```bash
cd /Users/vijayreddy/work_project/jobforge-ai

# Load environment variables
source .env

# Run migrations
poetry run alembic -c packages/database/alembic.ini upgrade head
```

#### 3. Start FastAPI Server (Terminal 1)

```bash
cd /Users/vijayreddy/work_project/jobforge-ai

# Run with auto-reload
poetry run uvicorn apps.web.main:app --reload --host 0.0.0.0 --port 8000

# Or without auto-reload
poetry run uvicorn apps.web.main:app --host 0.0.0.0 --port 8000
```

#### 4. Start Celery Worker (Terminal 2)

```bash
cd /Users/vijayreddy/work_project/jobforge-ai

# Run Celery worker
poetry run celery -A apps.worker.celery_app worker --loglevel=info --concurrency=4

# Or for single-process (debugging)
poetry run celery -A apps.worker.celery_app worker --loglevel=info --concurrency=1 --pool=solo
```

#### 5. Start Frontend (Optional - Terminal 3)

```bash
cd /Users/vijayreddy/work_project/jobforge-ai/apps/web/frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Will run on http://localhost:3000
```

---

## 📝 Common Commands

### Poetry Commands

```bash
# Activate virtual environment
poetry shell

# Run command in Poetry environment
poetry run python script.py
poetry run pytest

# Install specific package
poetry add package_name

# Update dependencies
poetry update

# Show installed packages
poetry show
poetry show --tree
```

### Docker Commands

```bash
# Set Docker socket (required for Rancher Desktop on Mac)
export DOCKER_HOST=unix://$HOME/.rd/docker.sock

# View containers
docker ps                           # Running containers
docker ps -a                        # All containers

# View images
docker images | grep infra

# View logs
docker logs container_name
docker logs -f container_name       # Follow logs
docker logs --tail 50 container_name # Last 50 lines

# Execute command in container
docker exec -it container_name bash
docker exec -it jobforge-postgres psql -U postgres

# Remove containers/images
docker-compose down                 # Stop and remove containers
docker-compose down -v              # Also remove volumes
docker rmi infra-web infra-worker   # Remove images

# Rebuild images
docker-compose build --no-cache     # Rebuild without cache
docker-compose build worker         # Rebuild specific service
```

### Database Commands

```bash
# Run migrations
poetry run alembic -c packages/database/alembic.ini upgrade head

# Create migration (auto-detect changes)
poetry run alembic -c packages/database/alembic.ini revision --autogenerate -m "Description"

# Downgrade migration
poetry run alembic -c packages/database/alembic.ini downgrade -1

# Current migration status
poetry run alembic -c packages/database/alembic.ini current

# Access PostgreSQL directly
psql -h localhost -U postgres -d jobforge_ai -c "SELECT version();"
```

### Testing Commands

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/unit/test_resume_analyzer.py

# Run with coverage
poetry run pytest --cov=packages --cov=services --cov=apps

# Run in verbose mode
poetry run pytest -v

# Run specific test
poetry run pytest tests/unit/test_file.py::test_function_name
```

### Code Quality Commands

```bash
# Format code
poetry run black .

# Lint code
poetry run ruff check . --fix

# Type checking
poetry run mypy packages services apps

# Format + Lint + Type check
poetry run black . && poetry run ruff check . --fix && poetry run mypy packages services apps
```

### Redis Commands

```bash
# Test Redis connection
redis-cli -h localhost -p 6379 PING
# Expected: PONG

# Access Redis CLI (if running in Docker)
export DOCKER_HOST=unix://$HOME/.rd/docker.sock
docker exec -it jobforge-redis redis-cli

# Inside Redis CLI
PING                    # Test connection
KEYS *                  # List all keys
GET key_name            # Get value
DEL key_name            # Delete key
FLUSHDB                 # Clear current database
FLUSHALL                # Clear all databases
```

---

## 🌐 API Documentation

### Access API Docs

**Interactive Documentation (Swagger UI):**
```
http://localhost:8000/docs
```

**Alternative Documentation (ReDoc):**
```
http://localhost:8000/redoc
```

### Health Check

```bash
# Check if API is running
curl http://localhost:8000/health

# Check API version (if implemented)
curl http://localhost:8000/api/v1/
```

### Example API Requests

```bash
# Upload resume
curl -X POST http://localhost:8000/api/v1/resume/upload \
  -F "file=@/path/to/resume.pdf"

# Create job preferences
curl -X POST http://localhost:8000/api/v1/preferences \
  -H "Content-Type: application/json" \
  -d '{
    "preferred_locations": ["San Francisco", "Remote"],
    "min_salary": 150000,
    "job_titles": ["Software Engineer", "Senior Developer"]
  }'

# Ingest a job
curl -X POST http://localhost:8000/api/v1/jobs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://linkedin.com/jobs/...",
    "source": "linkedin"
  }'
```

---

## 🔧 Troubleshooting

### Issue: "Redis cache not initialized"

**Solution:**
```bash
# Make sure Redis is running
docker ps | grep jobforge-redis

# Or start it
docker-compose up -d redis

# Clear Redis
redis-cli FLUSHDB
```

### Issue: "Connection refused" on port 5432

**Solution:**
```bash
# Start PostgreSQL container
docker-compose up -d postgres

# Verify it's running
docker ps | grep jobforge-postgres

# Test connection
psql -h localhost -U postgres -c "SELECT 1;"
```

### Issue: "Poetry: command not found"

**Solution:**
```bash
# Add to PATH
export PATH="$HOME/.local/bin:$PATH"

# Add to ~/.zshrc permanently
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Issue: "Docker socket not found"

**Solution:**
```bash
# Set Docker socket for Rancher Desktop
export DOCKER_HOST=unix://$HOME/.rd/docker.sock

# Add to ~/.zshrc permanently
echo 'export DOCKER_HOST=unix://$HOME/.rd/docker.sock' >> ~/.zshrc
source ~/.zshrc

# Verify socket exists
ls -la ~/.rd/docker.sock
```

### Issue: "Port 8000 already in use"

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or use different port
poetry run uvicorn apps.web.main:app --port 8001
```

### Issue: "Out of memory during Docker build"

**Solution:**
```bash
# Increase Docker memory in Rancher Desktop settings
# Then rebuild
docker-compose build --no-cache worker
```

---

## 📊 Project Structure

```
jobforge-ai/
├── apps/
│   ├── web/                 # FastAPI application
│   │   ├── main.py
│   │   ├── api/             # API routes
│   │   └── frontend/        # React/Next.js frontend (optional)
│   └── worker/              # Celery worker app
│       └── tasks/
├── packages/
│   ├── database/            # Database models & migrations
│   ├── common/              # Shared utilities
│   └── schemas/             # Pydantic schemas
├── services/
│   ├── resume_analyzer/     # Resume parsing
│   ├── jd_parser/          # Job description parsing
│   ├── scoring/            # Job scoring engine
│   └── decision_engine/    # Application decision logic
├── infra/
│   ├── docker/             # Docker files
│   │   ├── Dockerfile.web
│   │   └── Dockerfile.worker
│   └── docker-compose.yml  # Container orchestration
├── config/                 # Configuration files
├── tests/                  # Test suite
├── .env                    # Environment variables (local)
├── pyproject.toml          # Poetry configuration
└── local_run.md           # This file
```

---

## 📌 Quick Start (TL;DR)

```bash
# 1. Setup
export PATH="$HOME/.local/bin:$PATH"
export DOCKER_HOST=unix://$HOME/.rd/docker.sock
cd /Users/vijayreddy/work_project/jobforge-ai

# 2. Install dependencies
poetry install --no-root

# 3. Start services
cd infra && docker-compose up -d

# 4. Access application
# API: http://localhost:8000/docs
# Swagger UI: http://localhost:8000/docs
```

---

## 📞 Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Review this guide's troubleshooting section
3. Check API documentation at `/docs` endpoint
4. Review project README.md

---

## 📅 Last Updated
January 24, 2026

**Status:** ✅ All services operational and containerized
