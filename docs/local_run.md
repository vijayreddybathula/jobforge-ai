# 🚀 Local Development Setup Guide

Complete guide to run jobforge-ai locally with Docker and Poetry.

---

## 🖥️ System Requirements

### Prerequisites
- **macOS** (Apple Silicon or Intel)
- **Python 3.11+** (we recommend 3.13)
- **Rancher Desktop** or Docker Desktop (for container runtime)
- **Homebrew** (for package management)
- **OpenAI API Key** (for LLM features) - https://platform.openai.com/api-keys

### Optional
- **Node.js 18+** (for frontend development)
- **Git** (for version control)

### Verify Prerequisites

Before starting, run the validation script:

```bash
cd /path/to/jobforge-ai

# Make script executable
chmod +x init_setup.sh

# Run validation
./init_setup.sh
```

This will check:
- ✓ Python 3.11+
- ✓ Poetry installation
- ✓ Docker installation and daemon running
- ✓ Docker socket availability
- ✓ .env file configuration
- ✓ Available ports (8000, 5432, 6379)
- ✓ OpenAI API key configuration

---

## 📦 Installation Steps

### Step 1: Install Poetry (if not already installed)

```bash
# Install Poetry globally
curl -sSL https://install.python-poetry.org | python3 -

# Add to PATH (~/.zshrc or ~/.bashrc)
export PATH="$HOME/.local/bin:$PATH"

# Verify installation
poetry --version
```

### Step 2: Install Python Dependencies

```bash
cd /path/to/jobforge-ai

# Install all dependencies (creates virtual environment)
poetry install --no-root

# Activate the virtual environment (optional)
poetry shell

# Or use 'poetry run' prefix for individual commands
```

### Step 3: Start Docker Services

```bash
# Ensure Rancher Desktop is running
open -a "Rancher Desktop"

# Wait 30 seconds for Docker daemon to start

# Build and start all containers
docker-compose up --build

# In another terminal, verify containers are running:
docker-compose ps
```

### Step 4: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env  # (if available)

# Edit .env with your configuration
nano .env

# Required variables:
# - OPENAI_API_KEY=sk-proj-your-actual-key
# - DATABASE_URL=postgresql://postgres:jobforge_password@localhost:5432/jobforge_ai
# - REDIS_PASSWORD=redis_password
```

### Step 5: Run Database Migrations

```bash
# In a new terminal (with docker-compose still running)

# Wait for postgres to be ready
sleep 10

# Load environment and run migrations
source .env && poetry run alembic upgrade head

# Verify tables created
docker exec jobforge-postgres psql -U postgres -d jobforge_ai -c "\dt"
```

---

## 🐳 Running the Application

### Option A: Full Docker Stack (Recommended)

```bash
# In one terminal, start all services
docker-compose up

# Expected output:
# postgres_1  | database system is ready to accept connections
# redis_1     | Ready to accept connections
# web_1       | Uvicorn running on http://0.0.0.0:8000
# worker_1    | celery@... ready

# Access API documentation
open http://localhost:8000/docs

# View logs for any service
docker-compose logs web
docker-compose logs worker
docker-compose logs postgres
docker-compose logs redis
```

### Option B: Hybrid Mode (Local Services with Docker)

Useful for development when you want hot-reload on code changes:

```bash
# Terminal 1: Start only database services
docker-compose up postgres redis

# Terminal 2: Run FastAPI locally with auto-reload
poetry run uvicorn apps.web.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 3: Run Celery worker locally
poetry run celery -A apps.worker.celery_app worker --loglevel=info -c 4

# Access API
open http://localhost:8000/docs
```

---

## 🔧 Common Commands

### Docker Commands

```bash
# Start all services
docker-compose up

# Start in background
docker-compose up -d

# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# View service logs
docker-compose logs -f web          # Follow FastAPI logs
docker-compose logs -f worker       # Follow Celery logs
docker-compose logs -f postgres     # Follow PostgreSQL logs
docker-compose logs -f redis        # Follow Redis logs

# Rebuild images
docker-compose build --no-cache

# Access container shell
docker exec -it jobforge-web bash
docker exec -it jobforge-worker bash
docker exec -it jobforge-postgres bash
docker exec -it jobforge-redis redis-cli

# View running containers
docker ps
docker ps -a

# Remove all containers and images
docker system prune -a
```

### Poetry Commands

```bash
# Activate virtual environment
poetry shell

# Run command in venv
poetry run python script.py
poetry run pytest
poetry run black .

# Install new package
poetry add package_name

# Install dev dependency
poetry add --group dev package_name

# Show installed packages
poetry show

# Export requirements (for reference)
poetry export -f requirements.txt > requirements.txt
```

### Database Commands

```bash
# Connect to PostgreSQL
docker exec -it jobforge-postgres psql -U postgres -d jobforge_ai

# List tables
\dt

# Describe table
\d table_name

# Run query
SELECT * FROM artifact LIMIT 5;

# Exit
\q

# Run migration
source .env && poetry run alembic upgrade head

# Downgrade migration
source .env && poetry run alembic downgrade -1
```

### Redis Commands

```bash
# Connect to Redis
docker exec -it jobforge-redis redis-cli -a redis_password

# Get all keys
KEYS *

# Get specific key
GET key_name

# Delete key
DEL key_name

# Monitor commands
MONITOR

# Exit
QUIT
```

### Testing Commands

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/unit/test_scoring.py

# Run with coverage
poetry run pytest --cov=services

# Run with verbose output
poetry run pytest -v

# Run specific test
poetry run pytest tests/unit/test_scoring.py::test_score_job
```

### Code Quality Commands

```bash
# Format code
poetry run black .

# Check code style
poetry run flake8 .

# Type checking
poetry run mypy .

# Lint
poetry run pylint services/

# Check imports
poetry run isort --check-only .

# Auto-fix imports
poetry run isort .
```

---

## 📊 Service Details

### FastAPI Web Server
- **Port:** 8000
- **URL:** http://localhost:8000
- **Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Container:** jobforge-web
- **Entry Point:** apps/web/main.py
- **Auto-reload:** Enabled in hybrid mode, disabled in Docker

### PostgreSQL Database
- **Port:** 5432
- **Host:** localhost (hybrid) or postgres (Docker)
- **User:** postgres
- **Password:** jobforge_password (from .env)
- **Database:** jobforge_ai
- **Container:** jobforge-postgres
- **Image:** pgvector/pgvector:pg16
- **Data Path:** /var/lib/postgresql/data (volume: postgres_data)

### Redis Cache & Broker
- **Port:** 6379
- **Host:** localhost (hybrid) or redis (Docker)
- **Password:** redis_password (from .env)
- **Container:** jobforge-redis
- **Image:** redis:latest
- **Persistence:** Enabled with AOF (Append-Only File)
- **Data Path:** /data (volume: redis_data)

### Celery Worker
- **Container:** jobforge-worker
- **Workers:** 4 concurrent
- **Broker:** Redis
- **Tasks:** ingest_from_linkedin, ingest_job, parse_job, score_job
- **Loglevel:** INFO
- **Entry Point:** apps/worker/celery_app.py

---

## 🐛 Troubleshooting

### Issue 1: "Cannot connect to Docker daemon"

**Symptoms:** `Error response from daemon: Cannot connect to Docker daemon`

**Solutions:**
1. Start Rancher Desktop:
   ```bash
   open -a "Rancher Desktop"
   sleep 30  # Wait for daemon to start
   ```

2. Check Docker socket path:
   ```bash
   # Rancher Desktop (default)
   $HOME/.rd/docker.sock
   
   # Docker Desktop (alternative)
   /var/run/docker.sock
   
   # Set DOCKER_HOST if needed
   export DOCKER_HOST=unix://$HOME/.rd/docker.sock
   ```

### Issue 2: "Database password authentication failed"

**Symptoms:** `FATAL: password authentication failed for user postgres`

**Solutions:**
1. Verify .env file has correct password:
   ```bash
   grep POSTGRES_PASSWORD .env
   ```

2. Ensure DATABASE_URL matches:
   ```bash
   # Should be: postgresql://postgres:jobforge_password@localhost:5432/jobforge_ai
   grep DATABASE_URL .env
   ```

3. Reset database:
   ```bash
   docker-compose down -v
   docker-compose up postgres
   sleep 10
   source .env && poetry run alembic upgrade head
   ```

### Issue 3: "Port 8000 already in use"

**Symptoms:** `Address already in use` or `Port 8000 is already allocated`

**Solutions:**
1. Find process using port 8000:
   ```bash
   lsof -i :8000
   # Kill the process
   kill -9 <PID>
   ```

2. Or use different port:
   ```bash
   # In docker-compose.yml, change ports: "8001:8000"
   # Access at http://localhost:8001
   ```

### Issue 4: "Redis connection refused"

**Symptoms:** `Error 111 connecting to redis:6379. Connection refused.`

**Solutions:**
1. Check if Redis container is running:
   ```bash
   docker-compose ps redis
   ```

2. Restart Redis:
   ```bash
   docker-compose restart redis
   ```

3. Verify Redis password in .env:
   ```bash
   # Connect and test
   docker exec -it jobforge-redis redis-cli -a redis_password
   PING  # Should return PONG
   ```

### Issue 5: "ModuleNotFoundError" for packages

**Symptoms:** `ModuleNotFoundError: No module named 'services'`

**Solutions:**
1. Ensure you're using Poetry:
   ```bash
   poetry run python -c "import services"
   ```

2. Re-install dependencies:
   ```bash
   poetry install --no-root
   ```

3. In Docker, verify image was rebuilt:
   ```bash
   docker-compose build --no-cache web
   docker-compose up
   ```

### Issue 6: "Celery worker keeps restarting"

**Symptoms:** `worker_1  | Traceback... ModuleNotFoundError` then restart loop

**Solutions:**
1. Check worker logs:
   ```bash
   docker-compose logs -f worker
   ```

2. Rebuild worker image:
   ```bash
   docker-compose build --no-cache worker
   docker-compose up worker
   ```

3. Verify Redis is initialized before tasks:
   ```bash
   # Check apps/worker/celery_app.py has redis initialization at top
   grep -A5 "init_redis_cache" apps/worker/celery_app.py
   ```

### Issue 7: "Alembic migration fails"

**Symptoms:** `alembic.util.exc.CommandError: Can't locate revision identified by...`

**Solutions:**
1. Check migration status:
   ```bash
   source .env && poetry run alembic current
   ```

2. Reset migrations:
   ```bash
   docker-compose down -v
   docker-compose up postgres
   sleep 10
   source .env && poetry run alembic upgrade head
   ```

3. Create new migration if schema changed:
   ```bash
   source .env && poetry run alembic revision --autogenerate -m "describe change"
   source .env && poetry run alembic upgrade head
   ```

---

## 📚 API Documentation

Once running, access interactive API docs:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### Example API Calls

```bash
# Check API is running
curl http://localhost:8000/health

# Submit job ingestion (replace with actual endpoint)
curl -X POST http://localhost:8000/api/jobs/ingest \
  -H "Content-Type: application/json" \
  -d '{"job_url": "https://linkedin.com/jobs/..."}'

# Check job with ID
curl http://localhost:8000/api/jobs/<job_id>
```

---

## 📂 Project Structure

```
jobforge-ai/
├── apps/
│   ├── web/                 # FastAPI application
│   │   └── main.py         # Entry point
│   └── worker/             # Celery worker
│       └── celery_app.py   # Worker configuration
│
├── services/               # Core business logic
│   ├── apply_bot/
│   ├── decision_engine/
│   ├── jd_parser/          # Job description parser
│   ├── job_ingestion/      # Job data ingestion
│   ├── resume_analyzer/    # Resume analysis
│   └── scoring/            # Job scoring
│
├── packages/               # Shared utilities
│   ├── common/             # Common utilities (Redis, etc.)
│   ├── database/           # SQLAlchemy models & migrations
│   └── schemas/            # Pydantic schemas
│
├── config/                 # Configuration files
│   ├── candidate_profile.json
│   ├── cost_limits.yaml
│   ├── redis_config.yaml
│   ├── rules_config.yaml
│   └── scoring_weights.json
│
├── infra/                  # Infrastructure
│   ├── docker/             # Dockerfiles
│   └── docker-compose.yml  # Service orchestration
│
├── tests/                  # Test suite
│   ├── unit/
│   └── integration/
│
├── .env                    # Environment variables (create this)
├── pyproject.toml         # Poetry configuration
├── init_setup.sh          # Setup validation script
└── local_run.md          # This file
```

---

## ⚡ TL;DR Quick Start

```bash
# 1. Validate setup
chmod +x init_setup.sh && ./init_setup.sh

# 2. Edit .env with OpenAI key
nano .env  # Update OPENAI_API_KEY

# 3. Install dependencies
poetry install --no-root

# 4. Start Docker services
open -a "Rancher Desktop" && sleep 30
docker-compose up --build

# 5. In another terminal, run migrations
sleep 10 && source .env && poetry run alembic upgrade head

# 6. Access API
open http://localhost:8000/docs
```

---

## 📖 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/docs/)
- [Docker Documentation](https://docs.docker.com/)
- [Poetry Documentation](https://python-poetry.org/docs/)

---

## 🤝 Support

For issues or questions:
1. Check the **Troubleshooting** section above
2. Run `./init_setup.sh` to validate your setup
3. Check container logs: `docker-compose logs [service]`
4. Review `IMPLEMENTATION_SUMMARY.md` for architecture details
5. Contact the development team

---

**Last Updated:** 2024
**Python Version:** 3.11+
**Docker Compose Version:** 2.20+
