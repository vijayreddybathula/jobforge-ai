# JobForge AI Architecture Overview

![JobForge AI Architecture](https://raw.githubusercontent.com/vijayreddybathula/jobforge-ai/main/docs/assets/jobforge_architecture_diagram.png)

---

## System Summary

JobForge AI is a modular, scalable, LLM-powered job application platform. It automates job parsing, resume analysis, and candidate-job matching using Azure OpenAI, with robust data integrity and extensibility for production use.

---

## **Architecture Diagram**

```
+-------------------+        +-------------------+        +-------------------+
|                   |        |                   |        |                   |
|   User Interface  +------->+   FastAPI Web     +------->+   PostgreSQL DB   |
|  (Web/React/Etc)  |  REST  |   Server (API)    |  ORM   |  (users, jobs,    |
|                   |        |                   |        |   resumes, apps)  |
+-------------------+        +-------------------+        +-------------------+
         |                            |                            ^
         |                            v                            |
         |                  +-------------------+                  |
         |                  |                   |                  |
         +----------------->+   Redis           +------------------+
                            | (cache, broker)   |
                            +-------------------+
                                    |
                                    v
                            +-------------------+
                            |                   |
                            |   Celery Worker   |
                            | (background jobs) |
                            +-------------------+
                                    |
                                    v
                            +-------------------+
                            |                   |
                            | Azure OpenAI LLM  |
                            | (GPT-4, etc)      |
                            +-------------------+
```

---

## **Module Summaries**

### 1. **FastAPI Web Server**
- Exposes REST API endpoints for users, jobs, resumes, applications, scoring, etc.
- Handles authentication, validation, and orchestration of business logic.
- Integrates with Celery for background processing.

### 2. **PostgreSQL Database**
- Stores all persistent data: users, jobs, resumes, applications, scores, etc.
- Enforces data integrity with foreign key constraints.

### 3. **Redis**
- Used for caching frequently accessed data.
- Acts as the broker for Celery background tasks.

### 4. **Celery Worker**
- Executes background jobs (job parsing, resume analysis, scoring).
- Communicates with Redis and the database.

### 5. **Azure OpenAI**
- Provides LLM-powered parsing, analysis, and scoring.
- Used for extracting structured data from resumes and job descriptions, and for candidate-job matching.

---

## **API Flows**

### **A. User Flow**
- **Signup/Login:** User creates an account (email, password) via `/api/v1/users/`.
- **Profile/Preferences:** User can update profile and preferences (future endpoints).

### **B. Resume Flow**
- **Upload Resume:** User uploads resume via `/api/v1/resume/upload` (must exist in users table).
- **Resume Parsing:** LLM (Azure OpenAI) extracts skills, experience, etc.
- **Resume Storage:** Resume and parsed data saved in `resumes` table.

### **C. Job Flow**
- **Ingest/Create Job:** Admin or system ingests jobs via `/api/v1/jobs/ingest` or similar.
- **Job Parsing:** LLM extracts job requirements, skills, etc.

### **D. Application Flow**
- **Start Application:** User starts application for a job (`/api/v1/jobs/{job_id}/apply/assisted/start`).
- **Submit Application:** User submits application (`/api/v1/jobs/{job_id}/apply/submit`).
- **Scoring:** LLM scores fit between user and job.

---

## **Security & Extensibility**
- Passwords are hashed (bcrypt).
- Foreign key constraints ensure data integrity.
- Ready for JWT/OAuth integration for production.
- Modular: add endpoints for user update, password reset, admin, analytics, etc.

---

## **Summary Table**

| Module         | Purpose                                      |
|----------------|----------------------------------------------|
| FastAPI Web    | API endpoints, orchestration                 |
| PostgreSQL     | Persistent data storage                      |
| Redis          | Caching, Celery broker                       |
| Celery Worker  | Background processing                        |
| Azure OpenAI   | LLM-powered parsing, scoring, analysis       |

---

*For more details, see the code in each module or ask for a deep dive on any component!*
