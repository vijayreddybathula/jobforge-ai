# JobForge AI — Data Isolation & Multi-User Security Model

> This document is the authoritative reference for how user data is scoped,
> what is shared, what is private, and where the security boundary sits.

---

## 1. The Core Model

JobForge AI uses a **shared job catalog + per-user interaction** model.
This is the same pattern used by LinkedIn, Indeed, and Greenhouse:

```
┌─────────────────────────────────────────────────────────────┐
│                   GLOBAL (shared, no user_id)               │
│                                                             │
│   jobs_raw          ← the job posting text & metadata       │
│   jobs_parsed       ← LLM extraction of the JD              │
│                                                             │
│   Why shared? Same posting is the same for everyone.        │
│   No PII. Deduped by content_hash.                          │
└──────────────────────────────┬──────────────────────────────┘
                               │  same job_id referenced by ↓
┌──────────────────────────────▼──────────────────────────────┐
│              PER-USER (scoped to user_id FK)                │
│                                                             │
│   resumes            ← your resume file + parsed data       │
│   role_matches       ← roles suggested from YOUR resume     │
│   user_profiles      ← your skills, bullets (1 per user)    │
│   user_preferences   ← your salary/location/visa (1/user)   │
│   job_scores         ← YOUR fit score for a shared job      │
│   artifacts          ← YOUR pitch/bullets for a job         │
│   applications       ← YOUR application to a job            │
│   outcomes           ← YOUR interview results               │
│                                                             │
│   Key: UserA.job_score != UserB.job_score for same job.     │
│   Same Deloitte posting → Vijay scores 76, Jane scores 42.  │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. What UserA Can and Cannot See

| Data | UserA sees own? | UserA sees UserB's? | Why |
|---|---|---|---|
| Job postings (raw + parsed) | ✅ Yes | ✅ Yes (intentional) | Public catalog, no PII |
| Resume | ✅ Yes | ❌ Never | Personal document |
| Role matches | ✅ Yes | ❌ Never | Derived from resume |
| Profile | ✅ Yes | ❌ Never | Personal skills/bullets |
| Preferences | ✅ Yes | ❌ Never | Salary, visa, location |
| Job score | ✅ Yes | ❌ Never | Scored against own profile |
| Artifacts | ✅ Yes | ❌ Never | Generated from own resume |
| Applications | ✅ Yes | ❌ Never | Personal job hunt data |
| Outcomes | ✅ Yes | ❌ Never | Interview results |
| Feedback summary | ✅ Own only | ❌ Never | Calibration of own scoring |

---

## 3. Security Boundary: Where user_id Comes From

### Current state (INSECURE — pre-auth)
```
GET /jobs/{id}/score?user_id=<uuid>   ← ⚠️ anyone can forge this
POST /jobs/{id}/score?user_id=<uuid>  ← ⚠️ anyone can score as anyone
```
The `# TODO: Get from authenticated user` comment appears in every endpoint.
user_id is passed as a query param that any client can forge.

### Target state (SECURE — post-auth)
```python
# apps/web/auth.py
def get_current_user(x_user_id: str = Header(...), db: Session = Depends(get_db)) -> UUID:
    user = db.query(User).filter(User.user_id == x_user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or inactive user")
    return user.user_id

# Every endpoint uses Depends instead of a query param:
async def score_job(job_id: UUID, user_id: UUID = Depends(get_current_user), ...):
```

With this change:
- `user_id` is never accepted from the URL or request body for auth purposes
- The `X-User-ID` header is validated against the DB on every request
- Frontend stores user_id in localStorage after login and sends it as a header
- Forging a user_id returns 401 because the DB check fails

---

## 4. Auth Flow

```
┌──────────┐     POST /users/login          ┌──────────────┐
│  Browser │  ──{ email, password }────────▶│  FastAPI     │
│          │                                │              │
│          │  ◀──{ user_id, full_name }──── │  bcrypt check│
│          │                                └──────────────┘
│ Store in │
│ localStorage:
│  jf_session = {
│    user_id,
│    email,
│    full_name,
│    logged_in_at
│  }
│          │
│          │   All subsequent requests:
│          │  ──{ X-User-ID: <user_id> }───▶│  FastAPI     │
│          │                                │  validates   │
│          │                                │  vs DB       │
│          │  ◀──{ response data }───────── │              │
└──────────┘                                └──────────────┘
```

**Session expiry:** 8 hours from `logged_in_at`. Frontend checks on each page load.
**Logout:** Clear `jf_session` from localStorage, redirect to `/login`.

---

## 5. API Security Audit — Current Leaks

The following endpoints currently accept `user_id` as a query parameter
and MUST be migrated to `Depends(get_current_user)`:

| File | Endpoint | Issue |
|---|---|---|
| `scoring.py` | `POST /jobs/{id}/score` | user_id as query param |
| `scoring.py` | `GET /jobs/{id}/score` | user_id as query param |
| `apply.py` | `POST /jobs/{id}/apply/assisted/start` | hardcoded TODO |
| `apply.py` | `POST /jobs/{id}/apply/submit` | hardcoded TODO |
| `apply.py` | `POST /jobs/{id}/apply/cancel` | hardcoded TODO |
| `artifacts.py` | `POST /jobs/{id}/artifacts/generate` | check user_id source |
| `outcomes.py` | `GET /applications/feedback/summary` | no user filter at all |
| `preferences.py` | all endpoints | check user_id source |
| `resume.py` | all endpoints | check user_id source |

All will be fixed when `auth.py` is added and `Depends(get_current_user)` is applied.

---

## 6. New Endpoints Needed (with isolation requirement)

| Endpoint | Method | Isolation rule |
|---|---|---|
| `/users/login` | POST | Returns own user_id only |
| `/users/me/resumes` | GET | Returns only current user's resumes |
| `/resume/{id}` | DELETE | Must verify resume.user_id == current_user |
| `/jobs` | GET | Returns shared catalog + current user's scores only |
| `/jobs/score-all` | POST | Scores only for current user |
| `/applications` | GET | Returns only current user's applications |
| `/applications/feedback/summary` | GET | Aggregates only current user's outcomes |

---

## 7. DB Constraints Already Correct

No schema changes needed. Every per-user table already has:
- `user_id UUID NOT NULL REFERENCES users(user_id)`
- Indexed for fast per-user queries
- `job_scores` has composite index on `(job_id, user_id)` — supports the
  shared-catalog + per-user-score pattern perfectly

The only fix needed is at the **API layer**: replace forged query params with
`Depends(get_current_user)` so user_id comes from server-validated auth.
