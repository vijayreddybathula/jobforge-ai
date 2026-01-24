# Intelligent Apply Agent - Detailed Execution Plan (Updated)

This is the updated execution plan with comprehensive risk mitigation integrated and Redis cache properly configured throughout.

## Technology Stack (Updated)

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, Alembic
- **Frontend**: React + TypeScript (or Next.js)
- **Database**: PostgreSQL with pgvector extension (for embeddings)
- **Cache & Queue**: **Redis** (used for:
  - Celery/RQ task queue
  - LLM response caching (30-day TTL)
  - Session management
  - Rate limiting counters
  - User preferences caching
  - Scoring result caching
  - Job deduplication checks)
- **LLM**: OpenAI API (GPT-4 for parsing, GPT-3.5 for scoring)
- **Scraping**: Playwright for dynamic pages, requests for APIs
- **Storage**: Local filesystem (MVP) or S3-compatible storage
- **Vector DB**: pgvector (PostgreSQL extension) or separate vector DB

## Redis Cache Integration Points

### Phase 3: Resume Analysis
- **File**: `services/resume_analyzer/role_extractor.py`
  - Cache resume analysis results by resume hash (Redis key: `resume:analysis:{hash}`)
  - TTL: 30 days
  - Cache role extraction results to avoid re-analyzing same resume

### Phase 6: JD Parsing
- **File**: `services/jd_parser/jd_parser.py`
  - Cache parsed JD results by content hash (Redis key: `jd:parsed:{hash}`)
  - TTL: 30 days
  - Check cache before calling LLM API

### Phase 8: Scoring
- **File**: `services/scoring/scoring_service.py`
  - Cache scoring results for similar jobs (Redis key: `score:{job_id}:{profile_id}`)
  - TTL: 7 days
  - Cache embeddings for similarity matching

### Phase 4: User Preferences
- **File**: `apps/web/api/preferences.py`
  - Cache user preferences (Redis key: `user:prefs:{user_id}`)
  - TTL: 1 hour
  - Invalidate on update

### Phase 5: Job Ingestion
- **File**: `services/job_ingestion/rate_limiter.py`
  - Use Redis for distributed rate limiting
  - Track scraping sessions and cooldowns
  - Deduplication checks (Redis set: `jobs:seen:{hash}`)

### Phase 11: Apply Bot
- **File**: `services/apply_bot/session_manager.py`
  - Cache browser session state in Redis
  - Store cookies securely (encrypted)
  - Session timeout management

## Comprehensive Risk Mitigation

> **Full Details**: See [docs/risk_mitigation_strategy.md](docs/risk_mitigation_strategy.md) for complete implementation details, file paths, and monitoring strategies.

### 1. Web Scraping & Anti-Bot Detection

**Risk**: IP blocking, account suspension, CAPTCHA challenges, ToS violations

**Mitigation**:
- **File**: `services/job_ingestion/rate_limiter.py`
  - Rate limiting with exponential backoff (2-5s base delays, up to 30s on errors)
  - Redis-based distributed rate limiting
  - Per-source rate limits (LinkedIn: 10 jobs/hour, Glassdoor: 5 jobs/hour)
  - Respect `robots.txt` and implement cooldown periods

- **File**: `services/job_ingestion/scraping_monitor.py`
  - Monitor success/failure rates per source
  - Alert when failure rate > 20% for any source
  - Automatic pause and manual review trigger
  - CAPTCHA detection and automatic pause

- **File**: `services/job_ingestion/anti_detection.py`
  - User-agent rotation from pool of realistic browsers
  - IP rotation via proxy service (Bright Data, ScraperAPI) for production
  - Session management: Reuse authenticated sessions, refresh before expiry
  - Human-like behavior: Random mouse movements, variable typing speeds

- **File**: `config/scraping_policies.yaml`
  - Per-source policies and rate limits
  - Prefer official APIs (Greenhouse, Lever) over scraping
  - Fallback to manual URL input and job board APIs

**Redis Integration**: Use Redis for distributed rate limiting counters and session tracking

### 2. LLM API Costs & Reliability

**Risk**: High costs, rate limits, service outages, token limits

**Mitigation**:
- **File**: `services/common/llm_cache.py`
  - **Redis-based caching**: Cache LLM responses by content hash
  - Cache key format: `llm:response:{hash}` with 30-day TTL
  - Cache parsed JDs, resume analysis, scoring rationales
  - Target: >60% cache hit rate
  - Cache embeddings for similar JDs (cosine similarity > 0.95)

- **File**: `services/common/llm_cost_optimizer.py`
  - Use GPT-3.5-turbo for scoring (cheaper, sufficient quality)
  - Use GPT-4 only for JD parsing (requires structured output)
  - Batch requests when possible
  - Truncate long JDs to first 4000 tokens

- **File**: `services/common/llm_fallback.py`
  - Fallback chain: GPT-4 → GPT-3.5 → Local model (Ollama) → Rule-based
  - Retry with exponential backoff (max 3 retries)
  - Circuit breaker pattern: Stop calling API if error rate > 50%

- **File**: `config/llm_budget.yaml`
  - Daily/monthly budget limits per user
  - Alert when approaching limits (80%, 100%, 120%)
  - Automatic throttling when limits exceeded
  - Cost tracking per operation

**Redis Integration**: All LLM responses cached in Redis with content hash as key

### 3. Schema Validation & Parsing Failures

**Risk**: Invalid JSON, missing fields, inconsistent parsing quality

**Mitigation**:
- **File**: `services/jd_parser/validation_service.py`
  - Strict Pydantic validation with detailed error messages
  - Required field checks before storing
  - Type coercion for common issues

- **File**: `services/jd_parser/repair_service.py`
  - Automatic repair prompts when validation fails
  - Max 2 repair attempts before marking as `PARSE_FAILED`
  - Store raw LLM output for manual review

- **File**: `services/jd_parser/fallback_parser.py`
  - Rule-based extraction when LLM fails
  - Regex patterns for common fields
  - Keyword matching for skills

- **File**: `packages/schemas/jd_schema_flexible.py`
  - Flexible schema variant for partial parsing
  - Allow `UNKNOWN` values instead of failing
  - Store confidence scores per field

**Target**: >95% parse success rate

### 4. Apply Bot Failures & Browser Automation

**Risk**: Detection, selector failures, session timeouts, UI changes

**Mitigation**:
- **File**: `services/apply_bot/selector_manager.py`
  - Multiple selector strategies per field with fallback chain
  - Store selectors in database for easy updates
  - Version selectors per platform

- **File**: `services/apply_bot/human_like_behavior.py`
  - Random mouse movements and delays
  - Human-like typing speed
  - Scroll before interacting

- **File**: `services/apply_bot/session_recovery.py`
  - Save browser state in Redis (cookies, localStorage)
  - Resume sessions from saved state
  - Automatic re-authentication detection

- **File**: `services/apply_bot/error_recovery.py`
  - Retry failed field fills (max 2 attempts)
  - Skip optional fields if they fail
  - Detect CAPTCHA and pause
  - Comprehensive error logging with screenshots

- **File**: `services/apply_bot/manual_fallback.py`
  - Export filled form data as JSON
  - Always stop before final submit (human gate)

**Redis Integration**: Browser session state cached in Redis with encryption

### 5. Data Privacy & Security

**Risk**: Data breaches, unauthorized access, compliance violations

**Mitigation**:
- **File**: `packages/security/encryption.py`
  - Encrypt resumes at rest (AES-256)
  - Encrypt sensitive fields in database
  - Use environment variables for encryption keys

- **File**: `packages/security/access_control.py`
  - RBAC with JWT authentication
  - Rate limiting per user
  - Audit logging for all data access

- **File**: `packages/security/data_retention.py`
  - Configurable data retention policies
  - Secure deletion (overwrite before delete)
  - GDPR/CCPA compliance

- **File**: `packages/security/session_management.py`
  - Secure cookie storage (HttpOnly, Secure, SameSite)
  - Session timeout (30 minutes)
  - Session tokens stored in Redis with TTL

**Redis Integration**: Session tokens and user sessions stored in Redis with TTL

### 6. Legal & Compliance Risks

**Risk**: ToS violations, discrimination, unauthorized data collection

**Mitigation**:
- **File**: `docs/legal/terms_compliance.md`
  - Document ToS compliance per source
  - Prefer official APIs over scraping
  - User acknowledgment of ToS risks

- **File**: `services/scoring/fairness_monitor.py`
  - Audit scoring for bias
  - Remove protected characteristics from scoring
  - Transparent scoring breakdown

- **File**: `config/compliance_policies.yaml`
  - Opt-in consent for data processing
  - Clear privacy policy
  - User data deletion on request

- **File**: `services/apply_bot/compliance_gate.py`
  - Human-in-the-loop requirement
  - User confirmation for each application
  - Rate limiting to prevent spam

### 7. Data Quality & Accuracy

**Risk**: Incorrect matching, poor scoring, hallucinated content, stale data

**Mitigation**:
- **File**: `services/resume_analyzer/truth_validator.py`
  - Bullet library enforcement (no generation of new bullets)
  - Fact-checking against original resume
  - User review required for generated content

- **File**: `services/scoring/accuracy_monitor.py`
  - Track scoring accuracy vs. outcomes
  - A/B test different scoring weights
  - User feedback on score accuracy

- **File**: `services/job_ingestion/freshness_checker.py`
  - Detect stale jobs (>30 days)
  - Re-fetch job details before applying
  - Mark jobs as "expired" if unavailable

- **File**: `services/common/data_validation.py`
  - Validate all user inputs
  - Sanitize text inputs
  - Check data integrity

### 8. Scalability & Performance

**Risk**: DB degradation, queue backlog, API rate limits, storage costs

**Mitigation**:
- **File**: `packages/database/optimization.py`
  - Database indexes on all query paths
  - Connection pooling
  - Query optimization

- **File**: `services/common/queue_management.py`
  - Priority queues (high-score jobs first)
  - Horizontal scaling of workers (Celery)
  - Dead letter queue for failed jobs
  - **Redis-based queue**: Use Redis as Celery broker

- **File**: `services/common/storage_optimization.py`
  - Compress HTML snapshots (gzip)
  - Archive old snapshots to cold storage
  - Cleanup old data based on retention policy

- **File**: `services/common/redis_cache.py`
  - Redis for frequently accessed data
  - Cache parsed JDs (30-day TTL)
  - Cache user profiles and preferences (1-hour TTL)
  - Cache scoring results for similar jobs (7-day TTL)
  - Cache invalidation strategies

**Redis Integration**: Primary caching layer for all frequently accessed data

### 9. User Experience & Trust

**Risk**: Poor UI, unclear explanations, failed applications, downtime

**Mitigation**:
- **File**: `apps/web/frontend/src/components/ErrorBoundary.tsx`
  - Graceful error handling
  - Retry mechanisms
  - Loading states

- **File**: `apps/web/frontend/src/components/ScoreExplanation.tsx`
  - Clear visual score breakdown
  - Highlight strengths and gaps
  - Explain decision rationale

- **File**: `services/apply_bot/application_safety.py`
  - Always require human confirmation
  - Preview application before submission
  - Allow user to edit any auto-filled field

- **File**: `apps/web/api/health.py`
  - Health check endpoint
  - Status page showing system availability
  - Maintenance mode

### 10. Operational & Monitoring

**Risk**: Silent failures, lack of observability, difficult debugging

**Mitigation**:
- **File**: `packages/common/logging.py`
  - Structured logging (JSON format)
  - Correlation IDs for request tracing
  - Centralized log aggregation

- **File**: `packages/common/monitoring.py`
  - Key metrics: Jobs ingested/day, Parse success rate, Apply success rate, API costs
  - Alerts for critical failures (>10% error rate)
  - Dashboard for real-time monitoring

- **File**: `infra/backup/backup_strategy.py`
  - Daily database backups
  - Point-in-time recovery capability
  - Test restore procedures

- **File**: `infra/disaster_recovery/runbook.md`
  - Disaster recovery procedures
  - Failover strategies
  - Communication plan

**Redis Integration**: Use Redis for distributed locks, rate limiting, and session management

### 11. Cost Management

**Risk**: Uncontrolled LLM costs, infrastructure scaling, storage costs

**Mitigation**:
- **File**: `services/common/cost_tracking.py`
  - Track costs per operation
  - Daily/monthly cost reports
  - Budget alerts (80%, 100%, 120%)

- **File**: `config/cost_limits.yaml`
  - Per-user daily limits
  - Automatic throttling when limits exceeded
  - Cost optimization recommendations

**Redis Integration**: Track cost counters in Redis for distributed tracking

### 12. Testing & Quality Assurance

**Risk**: Production bugs, scoring errors, incorrect submissions

**Mitigation**:
- Unit tests (>80% coverage)
- Integration tests
- E2E tests
- All tests pass before merge
- Staging validation
- Gradual rollout (10% → 50% → 100%)

## Risk Monitoring Dashboard

**File**: `apps/web/frontend/src/pages/Admin/RiskDashboard.tsx`

Monitor in real-time:
- Scraping success rates per source
- LLM API costs and error rates
- Parse success rates
- Apply bot success rates
- Security events
- System performance metrics
- User satisfaction scores
- Cost trends and budget status
- **Redis cache hit rates and performance**

**Alert Thresholds**:
- Scraping failure rate > 20%: Pause source
- LLM error rate > 10%: Switch to fallback
- Parse success rate < 90%: Review prompts
- Apply bot failure rate > 15%: Manual review
- Security event: Immediate alert
- Cost > 120% of budget: Throttle operations
- Redis cache hit rate < 50%: Review caching strategy
- System downtime > 5 minutes: Escalate

## Redis Configuration

**File**: `config/redis_config.yaml`

```yaml
redis:
  host: localhost
  port: 6379
  db: 0
  password: ${REDIS_PASSWORD}
  
  # Cache configurations
  cache:
    llm_responses:
      ttl: 2592000  # 30 days
      key_prefix: "llm:response:"
    parsed_jds:
      ttl: 2592000  # 30 days
      key_prefix: "jd:parsed:"
    resume_analysis:
      ttl: 2592000  # 30 days
      key_prefix: "resume:analysis:"
    user_preferences:
      ttl: 3600  # 1 hour
      key_prefix: "user:prefs:"
    scoring_results:
      ttl: 604800  # 7 days
      key_prefix: "score:"
  
  # Queue configuration
  queue:
    broker_url: "redis://localhost:6379/1"
    result_backend: "redis://localhost:6379/2"
  
  # Session management
  sessions:
    ttl: 1800  # 30 minutes
    key_prefix: "session:"
  
  # Rate limiting
  rate_limiting:
    key_prefix: "ratelimit:"
    window: 3600  # 1 hour
```

## Implementation Notes

1. **Redis Setup**: Ensure Redis is included in Docker Compose with proper persistence
2. **Cache Strategy**: Implement cache-aside pattern for all LLM calls
3. **Cache Invalidation**: Clear relevant caches when data is updated
4. **Monitoring**: Track Redis memory usage and cache hit rates
5. **Fallback**: If Redis is unavailable, degrade gracefully (skip caching, not fail)

For complete risk mitigation details, see [docs/risk_mitigation_strategy.md](docs/risk_mitigation_strategy.md).
