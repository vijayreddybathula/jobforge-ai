# JobForge AI — Frontend UX Architecture

> **Stack:** React 18 + Vite + React Router v6 + TailwindCSS  
> **Auth:** Simple email/password → user_id session (localStorage)  
> **API Base:** `http://localhost:8000/api/v1`  
> **Design language:** Dark theme, card-based, minimal friction

---

## 1. Application Shell

```
┌─────────────────────────────────────────────────────────────────┐
│  SHELL (persistent across all authenticated pages)              │
│  ┌──────────┐  ┌─────────────────────────────────┐  ┌────────┐ │
│  │ JobForge │  │  ● Resume  ● Preferences  ● Jobs │  │ Vijay▾ │ │
│  └──────────┘  └─────────────────────────────────┘  └────────┘ │
└─────────────────────────────────────────────────────────────────┘
│                                                                  │
│                    <page content here>                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

Top nav with 3 primary sections. User avatar dropdown: Profile / Logout.

---

## 2. Route Map

```
/                       → redirect → /login (if unauth) or /dashboard (if auth)
/login                  → LoginPage
/signup                 → SignupPage
/dashboard              → DashboardPage          [protected]
/resume                 → ResumePage             [protected]
/resume/:id/roles       → RoleConfirmPage        [protected]
/preferences            → PreferencesPage        [protected]
/jobs                   → JobsPage               [protected]
/jobs/:id               → JobDetailPage          [protected]
/jobs/:id/artifacts     → ArtifactsPage          [protected]
/applications           → ApplicationsPage       [protected]
/outcomes               → OutcomesPage           [protected]
```

---

## 3. Screen Designs

---

### 3.1 LOGIN PAGE  `/login`

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│              ⚡ JobForge AI                          │
│         Intelligent Job Application Agent           │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │              Sign in to continue             │  │
│  │                                              │  │
│  │  Email                                       │  │
│  │  ┌────────────────────────────────────────┐  │  │
│  │  │  vijay@example.com                     │  │  │
│  │  └────────────────────────────────────────┘  │  │
│  │                                              │  │
│  │  Password                                    │  │
│  │  ┌────────────────────────────────────────┐  │  │
│  │  │  ••••••••                              │  │  │
│  │  └────────────────────────────────────────┘  │  │
│  │                                              │  │
│  │  [          Sign In          ]               │  │
│  │                                              │  │
│  │  Don't have an account? Sign up →            │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Behavior:**
- `POST /api/v1/users/login` → returns `{ user_id, email, full_name }`
- Store in `localStorage` as `jf_session`
- Redirect to `/dashboard`
- Error states: wrong password, user not found

---

### 3.2 SIGNUP PAGE  `/signup`

```
┌─────────────────────────────────────────────────────┐
│              ⚡ JobForge AI                          │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │              Create your account             │  │
│  │                                              │  │
│  │  Full Name          Email                    │  │
│  │  ┌────────────┐     ┌────────────────────┐   │  │
│  │  │ Vijay R.   │     │ vijay@example.com  │   │  │
│  │  └────────────┘     └────────────────────┘   │  │
│  │                                              │  │
│  │  Password                                    │  │
│  │  ┌────────────────────────────────────────┐  │  │
│  │  │  ••••••••                              │  │  │
│  │  └────────────────────────────────────────┘  │  │
│  │                                              │  │
│  │  [          Create Account       ]           │  │
│  │                                              │  │
│  │  Already have an account? Sign in →          │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Behavior:**
- `POST /api/v1/users` → creates user, auto-login
- Redirect to `/resume` (onboarding flow start)

---

### 3.3 DASHBOARD  `/dashboard`

```
┌─────────────────────────────────────────────────────────────────┐
│ NAV: ⚡ JobForge AI    Resume | Preferences | Jobs    Vijay ▾    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Good morning, Vijay 👋                                         │
│  Here's your pipeline status                                    │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ RESUME   │  │  JOBS    │  │  SCORED  │  │ TO APPLY │       │
│  │          │  │          │  │          │  │          │       │
│  │   ✓      │  │   10     │  │   8/10   │  │    3     │       │
│  │ Uploaded │  │ in pipe  │  │  scored  │  │ APPLY    │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                 │
│  ── Pipeline Health ──────────────────────────────────────     │
│                                                                 │
│  Onboarding checklist:                                          │
│  ✅ Resume uploaded                                             │
│  ✅ Roles confirmed                                             │
│  ✅ Preferences set                                             │
│  ✅ Jobs searched                                               │
│  ⬜ Applications submitted  →  [Go to Jobs]                     │
│  ⬜ Outcomes recorded       →  [Go to Applications]             │
│                                                                 │
│  ── Recent Activity ──────────────────────────────────────     │
│  • Deloitte Senior GenAI Engineer  — scored 76 — APPLY         │
│  • OpenAI AI Deployment Engineer   — scored 82 — APPLY         │
│  • Charles Schwab Lead AI Dev      — scored 71 — VALIDATE      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**API calls:**
- `GET /resume/roles/{resume_id}` — check resume exists
- `GET /preferences` — check preferences set
- `GET /profile` — check profile built
- Recent scores from local session cache

---

### 3.4 RESUME PAGE  `/resume`

```
┌─────────────────────────────────────────────────────────────────┐
│ NAV                                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📄 Resume                             [+ Upload New Resume]    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  vijay_reddybathula.docx          v1   Jan 25, 2026     │   │
│  │  ✓ Parsed   ✓ Analyzed                                  │   │
│  │                                                         │   │
│  │  [View Roles]  [Re-analyze]  [Delete]                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ── Upload Zone (drag & drop) ──────────────────────────────   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │         📁 Drop your resume here                        │   │
│  │         PDF or DOCX · Max 10MB                          │   │
│  │         [Browse files]                                  │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Note: Uploading a new resume will create a new version.        │
│  Your existing applications will not be affected.               │
└─────────────────────────────────────────────────────────────────┘
```

**API calls:**
- `GET /users/{user_id}/resumes` — list resumes (needs new endpoint)
- `POST /resume/upload` — upload
- `POST /resume/analyze/{id}` — trigger analysis
- `DELETE /resume/{id}` — delete (needs new endpoint)

---

### 3.5 ROLE CONFIRM PAGE  `/resume/:id/roles`

```
┌─────────────────────────────────────────────────────────────────┐
│ NAV                                    ← Back to Resume         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🎯 Confirm Your Target Roles                                   │
│  Based on your resume analysis. Select all that apply.          │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ☑  Senior GenAI Engineer              confidence: 95%  │   │
│  │     Python · Azure OpenAI · RAG · Multi-agent           │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ☑  AI/ML Engineer                     confidence: 87%  │   │
│  │     LLM · Vector DB · FastAPI · Azure                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ☐  Senior Backend Engineer            confidence: 72%  │   │
│  │     Python · FastAPI · PostgreSQL · Redis               │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ☐  Solutions Architect                confidence: 68%  │   │
│  │     Azure · Microservices · API Design                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  + Add custom role    ┌──────────────────────────────┐         │
│                       │  e.g. Staff AI Engineer       │         │
│                       └──────────────────────────────┘         │
│                                                                 │
│  [  Save & Build Profile  ]   → builds UserProfile from roles  │
└─────────────────────────────────────────────────────────────────┘
```

**API calls:**
- `GET /resume/roles/{resume_id}` — load suggested roles
- `POST /resume/roles/confirm` — confirm selected
- `POST /profile/build-from-resume/{resume_id}` — auto-trigger after confirm

---

### 3.6 PREFERENCES PAGE  `/preferences`

```
┌─────────────────────────────────────────────────────────────────┐
│ NAV                                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ⚙️  Job Preferences                    [Save Changes]          │
│                                                                 │
│  ── Work Authorization ─────────────────────────────────────   │
│  Visa Status      ┌──────────────────────┐                      │
│                   │ US Citizen           ▾│                      │
│                   └──────────────────────┘                      │
│                                                                 │
│  ── Location Preferences ───────────────────────────────────   │
│  ☑ Remote    ☑ Hybrid    ☐ Onsite only                         │
│                                                                 │
│  Preferred Cities (optional)                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Dallas, TX  ×    Remote  ×    [+ Add city]             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ── Compensation ────────────────────────────────────────────  │
│  Minimum Base ($)     Maximum Base ($)                          │
│  ┌──────────────┐     ┌──────────────┐                         │
│  │  100,000     │     │  200,000     │                         │
│  └──────────────┘     └──────────────┘                         │
│                                                                 │
│  ── Company Preferences ─────────────────────────────────────  │
│  Company Size   ☑ Startup   ☑ Mid-size   ☐ Enterprise          │
│  Industries     ☑ Tech   ☑ Finance   ☐ Healthcare   ☐ Other    │
│                                                                 │
│  [  Save Preferences  ]                                         │
└─────────────────────────────────────────────────────────────────┘
```

**API calls:**
- `GET /preferences` — load existing
- `POST /preferences` — create (first time)
- `PUT /preferences` — update

---

### 3.7 JOBS PAGE  `/jobs`

```
┌─────────────────────────────────────────────────────────────────┐
│ NAV                                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  💼 Job Pipeline          [🔍 Search New Jobs]  [⚡ Score All]  │
│                                                                 │
│  Filter: [All ▾]  [Verdict ▾]  [Source ▾]   🔎 Search titles   │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 76  Senior GenAI Engineer          Deloitte              │  │
│  │     Dallas, TX · jsearch · Parsed                        │  │
│  │     [ASSISTED_APPLY]                                     │  │
│  │     [Score ↻] [Artifacts ✨] [View JD 📋] [Apply 🚀]    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  —  AI/ML Engineer                 General Dynamics      │  │
│  │     Remote · jsearch · Parsed                            │  │
│  │     [NOT SCORED]                                         │  │
│  │     [⚡ Score]  [View JD 📋]                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 82  AI Deployment Engineer          OpenAI               │  │
│  │     Remote · jsearch · Parsed                            │  │
│  │     [ASSISTED_APPLY]                                     │  │
│  │     [Score ↻] [Artifacts ✨] [View JD 📋] [Apply 🚀]    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Showing 10 of 10 jobs                    [Load More]          │
└─────────────────────────────────────────────────────────────────┘
```

**Requires new API:** `GET /jobs?page=1&limit=20` — list all jobs with status

**API calls:**
- `GET /jobs` — paginated list (NEW endpoint needed)
- `POST /jobs/{id}/score` — score individual
- `POST /jobs/score-all` — batch score (NEW endpoint needed)
- `GET /jobs/{id}/parsed` — view JD

---

### 3.8 JOB DETAIL PAGE  `/jobs/:id`

```
┌─────────────────────────────────────────────────────────────────┐
│ NAV                                    ← Back to Jobs           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Senior GenAI Engineer — Deloitte                 Score: 76    │
│  Dallas, TX · Full-time · Hybrid · jsearch                      │
│                                                                 │
│  [ASSISTED_APPLY]  [🚀 Start Apply]  [✨ Generate Artifacts]    │
│                                                                 │
│  ┌──────────────────────────────┐  ┌──────────────────────────┐ │
│  │  SCORE BREAKDOWN             │  │  PARSED JD               │ │
│  │                              │  │                          │ │
│  │  Core Skills    ████████ 100 │  │  Role: Senior GenAI Eng  │ │
│  │  Nice-to-have   ████░░░░  50 │  │  Seniority: Senior       │ │
│  │  Seniority      ███████░  80 │  │  Location: Hybrid        │ │
│  │  Domain         ██████░░  70 │  │                          │ │
│  │  Location       ████████  80 │  │  Must-haves:             │ │
│  │  Compensation   █████░░░  50 │  │  • GenAI / AI-ML         │ │
│  │                              │  │  • Software Engineering  │ │
│  │  Rationale:                  │  │  • Python / Java         │ │
│  │  Strong skill match. Comp    │  │                          │ │
│  │  range unknown.              │  │  Red flags:              │ │
│  │                              │  │  • No salary disclosed   │ │
│  └──────────────────────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.9 ARTIFACTS PAGE  `/jobs/:id/artifacts`

```
┌─────────────────────────────────────────────────────────────────┐
│ NAV                                    ← Back to Job            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✨ Application Artifacts — Deloitte Senior GenAI Engineer      │
│                                                                 │
│  [Generate All]  Last generated: never                          │
│                                                                 │
│  ┌── 🎯 Recruiter Pitch ─────────────────────────────────────┐  │
│  │  With over five years of experience as a Senior GenAI...  │  │
│  │                                              [📋 Copy]    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌── 📄 Tailored Resume Bullets ─────────────────────────────┐  │
│  │  Summary: Experienced Senior GenAI Engineer with...       │  │
│  │                                                           │  │
│  │  • Led RAG pipeline architecture using PGVector...        │  │
│  │  • Built multi-agent workflows with Azure OpenAI...       │  │
│  │  • Deployed containerized AI services on AKS...           │  │
│  │                                                           │  │
│  │  Source bullets: VR-001, VR-002, VR-008                   │  │
│  │  ATS Keywords: GenAI, AI/ML, Python, Azure                │  │
│  │                                         [📋 Copy All]     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌── 💬 Application Answers ─────────────────────────────────┐  │
│  │  Why interested?                                          │  │
│  │  I'm excited about this role because...  [📋 Copy]        │  │
│  │                                                           │  │
│  │  Why this company?                                        │  │
│  │  Your focus on AI innovation...          [📋 Copy]        │  │
│  │  [Show all 6 answers ▾]                                   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  [🚀 Proceed to Apply →]                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.10 APPLICATIONS PAGE  `/applications`

```
┌─────────────────────────────────────────────────────────────────┐
│ NAV                                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📬 Applications                                                │
│                                                                 │
│  Filter: [All ▾]  [Status ▾]                                   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Deloitte — Senior GenAI Engineer                        │  │
│  │  Submitted: Mar 9, 2026  ·  Mode: Assisted               │  │
│  │  Status: [SUBMITTED]                                     │  │
│  │  [Record Outcome ▾]                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  OpenAI — AI Deployment Engineer                         │  │
│  │  Started: Mar 9, 2026   ·  Mode: Assisted                │  │
│  │  Status: [STARTED]                                       │  │
│  │  [Mark Submitted]  [Cancel]                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ── Feedback Summary ────────────────────────────────────────  │
│  Score 75-84:  3 applied  →  1 callback  (33%)                 │
│  Score 85+:    0 applied                                        │
│  Insight: Insufficient data. Keep recording outcomes.           │
└─────────────────────────────────────────────────────────────────┘
```

**API calls:**
- `GET /applications` — list (NEW endpoint needed)
- `POST /applications/{id}/outcome` — record stage
- `GET /applications/feedback/summary` — calibration

---

## 4. New Backend Endpoints Required

The following API endpoints are needed by the frontend but don't exist yet:

| Endpoint | Method | Purpose |
|---|---|---|
| `/users/login` | POST | Email+password → user_id |
| `/users/{id}/resumes` | GET | List user's resumes |
| `/resume/{id}` | DELETE | Delete a resume |
| `/jobs` | GET | Paginated job list with score+parse status |
| `/jobs/score-all` | POST | Batch score all unscored jobs |
| `/applications` | GET | List user's applications |

---

## 5. Component Tree

```
src/
  main.jsx                    # Vite entry point
  App.jsx                     # Router + AuthProvider
  contexts/
    AuthContext.jsx            # user session (localStorage)
  hooks/
    useAuth.js
    useApi.js                  # fetch wrapper with user_id header
  pages/
    LoginPage.jsx
    SignupPage.jsx
    DashboardPage.jsx
    ResumePage.jsx
    RoleConfirmPage.jsx
    PreferencesPage.jsx
    JobsPage.jsx
    JobDetailPage.jsx
    ArtifactsPage.jsx
    ApplicationsPage.jsx
  components/
    layout/
      Shell.jsx                # top nav + outlet
      ProtectedRoute.jsx
    resume/
      ResumeCard.jsx
      UploadZone.jsx
      RoleCard.jsx
    jobs/
      JobCard.jsx
      ScoreBreakdown.jsx
      VerdictBadge.jsx
      ScoreCircle.jsx
      SearchModal.jsx
    artifacts/
      PitchBlock.jsx
      BulletsBlock.jsx
      AnswersBlock.jsx
    preferences/
      PreferencesForm.jsx
    common/
      Button.jsx
      Modal.jsx
      Toast.jsx
      Spinner.jsx
      EmptyState.jsx
      ProgressChecklist.jsx
```

---

## 6. User Journey (happy path)

```
1. /signup          → create account
2. /resume          → upload resume → auto-analyze triggered
3. /resume/:id/roles → confirm target roles → build profile
4. /preferences     → set salary/location/visa constraints
5. /jobs            → search jobs (modal) → auto-parse
6. /jobs            → score all jobs
7. /jobs/:id        → review score breakdown + red flags
8. /jobs/:id/artifacts → generate pitch + resume bullets + answers
9. /jobs/:id        → start assisted apply → review → submit
10. /applications   → record outcome (phone screen / offer / rejected)
11. /applications   → view feedback summary → calibrate
```

---

## 7. Auth Flow Detail

```
POST /api/v1/users/login
  body: { email, password }
  response: { user_id, email, full_name }
  → store in localStorage as:
    jf_session = { user_id, email, full_name, logged_in_at }

All subsequent API calls:
  headers: { 'x-user-id': session.user_id }

Logout:
  → clear localStorage → redirect to /login

ProtectedRoute:
  → if no jf_session → redirect to /login
  → if session expired (>8h) → redirect to /login with message
```

---

## 8. Tech Stack Decisions

| Concern | Choice | Why |
|---|---|---|
| Framework | React 18 + Vite | Fast HMR, minimal config |
| Routing | React Router v6 | Standard SPA routing |
| Styling | TailwindCSS | Utility-first, dark theme easy |
| State | React Context + useState | No Redux needed at this scale |
| HTTP | fetch (custom hook) | No extra dependency |
| Icons | lucide-react | Lightweight, consistent |
| File upload | react-dropzone | Drag and drop |
| Notifications | custom Toast | No library needed |

---

## 9. Build & Dev Setup

```bash
# Setup
cd apps/web-ui
npm create vite@latest . -- --template react
npm install react-router-dom tailwindcss lucide-react react-dropzone
npx tailwindcss init -p

# Dev
npm run dev   # runs on http://localhost:5173

# Proxy API (vite.config.js)
server: {
  proxy: {
    '/api': 'http://localhost:8000'
  }
}
```

---

## 10. Implementation Order

| Sprint | Pages | New API endpoints |
|---|---|---|
| Sprint 1 | Login, Signup, Shell | `POST /users/login` |
| Sprint 2 | Resume, Role Confirm | `GET /users/{id}/resumes`, `DELETE /resume/{id}` |
| Sprint 3 | Preferences | (all exist) |
| Sprint 4 | Jobs, Job Detail | `GET /jobs`, `POST /jobs/score-all` |
| Sprint 5 | Artifacts | (all exist) |
| Sprint 6 | Applications, Outcomes | `GET /applications` |
