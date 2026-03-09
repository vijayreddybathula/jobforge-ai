# JobForge AI — Frontend

React 18 + Vite + TailwindCSS + React Router v6

## Setup

```bash
cd apps/web-ui
npm install
npm run dev
```

Runs on http://localhost:5173  
API proxied to http://localhost:8000 via Vite

## Auth

Login stores `jf_session` in localStorage with:
```json
{ "user_id": "...", "email": "...", "full_name": "...", "logged_in_at": "..." }
```
All API calls send `X-User-ID: <user_id>` header automatically via `useApi()` hook.
Session expires after 8 hours.

## Data Isolation

- Jobs are **shared** catalog (no user_id) — same posting visible to all users
- Scores, artifacts, applications, outcomes are **per-user** — enforced by backend
- `useApi()` hook always attaches the authenticated user's ID
- 401 responses auto-logout and redirect to /login

## Pages

| Route | Page |
|---|---|
| /login | LoginPage |
| /signup | SignupPage |
| /dashboard | DashboardPage |
| /resume | ResumePage |
| /resume/:id/roles | RoleConfirmPage |
| /preferences | PreferencesPage |
| /jobs | JobsPage |
| /jobs/:id | JobDetailPage |
| /jobs/:id/artifacts | ArtifactsPage |
| /applications | ApplicationsPage |
