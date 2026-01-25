# Setup Guide for Team Members

> **For your friend (or any team member):** This explains how to set up jobforge-ai on their local machine.

---

## TL;DR - Get Running in 5 Minutes

```bash
# 1. Clone or get the project files
cd jobforge-ai

# 2. Validate your system is ready
chmod +x init_setup.sh
./init_setup.sh

# 3. Follow the output and fix any issues reported

# 4. If all checks pass:
nano .env  # Add your OpenAI API key

# 5. Start the services
poetry install --no-root
docker-compose up --build

# 6. Run migrations (in another terminal)
sleep 10
source .env && poetry run alembic upgrade head

# 7. Access the API
open http://localhost:8000/docs
```

---

## Why Docker? Why is this reliable?

We use Docker because:

✅ **No Local Environment Issues** - Everything runs in containers with exact same dependencies
✅ **Reproducible** - Exact same versions of Python, PostgreSQL, Redis across all machines
✅ **Isolated** - Services don't interfere with your system
✅ **Easy Cleanup** - `docker-compose down -v` removes everything cleanly

**Result:** Your friend's setup should work identical to yours.

---

## What Your Friend Needs (Prerequisites)

1. **Rancher Desktop** or Docker Desktop
   - Provides Docker runtime
   - ~5 minute install
   - ~1GB disk space

2. **Python 3.11+** (usually already installed on Mac)
   ```bash
   python3 --version  # Check if you have it
   ```

3. **Poetry** (Python package manager)
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

4. **OpenAI API Key** (free with credits)
   - Get from: https://platform.openai.com/api-keys
   - Keep it secret ⛔

---

## The Two Validation Tools We Created

### 1. `init_setup.sh` - Pre-flight Checklist

Runs **before** any setup to catch problems:

```bash
./init_setup.sh
```

This checks:
- ✓ Is Python 3.11+ installed?
- ✓ Is Poetry installed?
- ✓ Is Docker installed?
- ✓ Is Docker daemon running?
- ✓ Can Docker access its socket?
- ✓ Is .env file configured?
- ✓ Are ports 8000, 5432, 6379 available?
- ✓ Is OpenAI API key set?

**Output:** Color-coded results with specific error messages

If any fail, it tells your friend exactly what to fix.

### 2. `local_run.md` - Complete Setup Guide

Comprehensive 400+ line guide with:
- System requirements checklist
- Step-by-step installation
- Two ways to run (full Docker / hybrid mode)
- All common commands (Docker, Poetry, Database, Testing)
- 7 common issues + solutions
- API documentation
- Troubleshooting guide

---

## What Could Still Go Wrong?

### ❌ **Should NOT Happen with Docker:**
- ❌ "Package X not found" - Docker has all packages
- ❌ "Wrong Python version" - Docker uses fixed Python 3.13
- ❌ "Database connection string" - It's in .env
- ❌ "Missing dependencies" - Poetry installs them

### ⚠️ **Could Happen (but rare):**
1. **Rancher Desktop not installed**
   - Fix: `brew install rancher`

2. **Docker socket not at expected path**
   - Rancher Desktop: `~/.rd/docker.sock`
   - Docker Desktop: `/var/run/docker.sock`
   - Fix: `export DOCKER_HOST=unix://...` (init_setup.sh detects this)

3. **OpenAI API key not configured**
   - Fix: Add to .env file
   - The app will still run but LLM features won't work

4. **Ports already in use**
   - Fix: Change in docker-compose.yml or kill process on port
   - init_setup.sh checks for this

5. **Disk space issues**
   - Docker images: ~3GB
   - Database volumes: varies
   - Fix: `docker system prune` to clean up old images

---

## Instructions for Your Friend

**Share these files with your friend:**
- `local_run.md` - Complete setup guide
- `init_setup.sh` - Validation script
- `.env.example` - Configuration template (create if needed)

**Your friend should:**

### Step 1: Verify Prerequisites
```bash
chmod +x init_setup.sh
./init_setup.sh
```
- Takes 1 minute
- Reports what's missing
- Gives specific fix instructions

### Step 2: If All Checks Pass
```bash
# Install Python dependencies
poetry install --no-root

# Edit configuration with their OpenAI key
nano .env  # Add: OPENAI_API_KEY=sk-proj-...

# Start all services
docker-compose up --build
```
- Takes 5-10 minutes first time (downloads/builds containers)
- ~1 minute on subsequent runs
- Will show "ready to accept connections" for each service

### Step 3: Run Database Migrations
```bash
# In another terminal, after docker-compose has started
sleep 10
source .env && poetry run alembic upgrade head
```
- Creates database tables
- Should complete in <1 second

### Step 4: Verify It Works
```bash
# Check all containers are running
docker-compose ps

# Access the API
open http://localhost:8000/docs

# Or test from terminal
curl http://localhost:8000/health
```

---

## Expected Output (Success Case)

When everything works, your friend will see:

```
CONTAINER ID   IMAGE              STATUS
abc123...      jobforge-postgres  Up 2 minutes (healthy)
def456...      jobforge-redis     Up 2 minutes (healthy)
ghi789...      jobforge-web       Up 1 minute (healthy)
jkl012...      jobforge-worker    Up 1 minute

Celery Worker Ready:
celery@ghi789 ready.

API Running:
INFO: Uvicorn running on http://0.0.0.0:8000
```

Access: http://localhost:8000/docs

---

## What Each Service Does

| Service | What | Port | Health Check |
|---------|------|------|--------------|
| **PostgreSQL** | Database | 5432 | `docker-compose ps` shows ✓ |
| **Redis** | Cache + Message Queue | 6379 | `redis-cli PING` returns PONG |
| **FastAPI Web** | Main API | 8000 | `curl localhost:8000/health` |
| **Celery Worker** | Background tasks | — | `docker-compose logs worker` shows "ready" |

---

## Common Commands Your Friend Will Need

```bash
# See if everything is running
docker-compose ps

# View logs for debugging
docker-compose logs -f web      # FastAPI logs
docker-compose logs -f worker   # Celery logs
docker-compose logs -f postgres # Database logs

# Stop everything cleanly
docker-compose down

# Remove all data and start fresh
docker-compose down -v

# Connect to database
docker exec -it jobforge-postgres psql -U postgres -d jobforge_ai

# Connect to Redis
docker exec -it jobforge-redis redis-cli -a redis_password

# Run tests
poetry run pytest

# Format code
poetry run black .
```

---

## Troubleshooting Decision Tree

```
┌─ Run: ./init_setup.sh
│
├─ All ✓ checks pass?
│  ├─ YES → Go to: "Configure .env"
│  └─ NO  → Follow fix instructions in output
│
├─ Configure .env
│  └─ Add OpenAI key: OPENAI_API_KEY=sk-proj-...
│
├─ Run: docker-compose up --build
│  ├─ Starts successfully? → Go to: "Test API"
│  └─ Error? → See troubleshooting section in local_run.md
│
├─ Test API
│  └─ Can access http://localhost:8000/docs?
│     ├─ YES → 🎉 Success! App is running
│     └─ NO  → Check docker-compose logs
│
└─ Having issues?
   └─ Look up the problem in: local_run.md → Troubleshooting section
```

---

## Is It Really "No Local Issues"?

**In Docker:** Yes, with caveats:

✅ **Will Work Identically:**
- Same Python version (3.13)
- Same PostgreSQL (16 with pgvector)
- Same Redis configuration
- Same FastAPI/Celery versions
- Same dependencies

⚠️ **Still Requires:**
- Docker/Rancher Desktop installed
- Python 3.11+ on their Mac
- OpenAI API key
- Available ports (8000, 5432, 6379)

✅ **Will NOT Have:**
- "Works on my Mac but not on yours" issues
- Library version conflicts
- Missing dependencies
- PostgreSQL compatibility problems
- Redis configuration differences

---

## Support Matrix

| Issue | Check This | Run This |
|-------|-----------|----------|
| "Docker daemon not running" | Rancher Desktop | `open -a "Rancher Desktop"` |
| "Port 8000 in use" | Other processes | `lsof -i :8000` |
| "Database connection failed" | .env file | `grep DATABASE_URL .env` |
| "Redis password error" | Redis config | `docker-compose logs redis` |
| "Celery worker keeps restarting" | Worker logs | `docker-compose logs -f worker` |
| "Unknown module error" | Dependencies | `poetry install --no-root` |
| "API not responding" | Container health | `docker-compose ps` |

---

## Final Checklist

Your friend should verify:

- [ ] Rancher Desktop or Docker Desktop installed
- [ ] Python 3.11+ available: `python3 --version`
- [ ] Poetry installed: `poetry --version`
- [ ] init_setup.sh passes all checks: `./init_setup.sh`
- [ ] .env file configured with OpenAI key
- [ ] docker-compose up runs without errors
- [ ] All containers show "Up" status
- [ ] API accessible at http://localhost:8000/docs
- [ ] Database migrations complete: `poetry run alembic current`
- [ ] Celery worker shows "ready" in logs

---

## Questions?

If your friend gets stuck:

1. **First:** Run `./init_setup.sh` - it diagnoses 80% of issues
2. **Second:** Check `local_run.md` Troubleshooting section
3. **Third:** Share the error message + `docker-compose logs`
4. **Last:** Contact you with exact error output

---

**Version:** 1.0  
**Last Updated:** 2024  
**Tested On:** macOS 12+, Apple Silicon & Intel
