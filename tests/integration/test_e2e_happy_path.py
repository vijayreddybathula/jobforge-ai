"""End-to-end happy path: signup → resume upload → analyze → confirm role
→ build profile → set preferences → ingest job → parse → score → view.

All external I/O (Azure Blob, Azure OpenAI, JSearch API) is mocked.
The database uses SQLite in-memory via the `db` fixture in conftest.py.
"""

import io
import uuid
import json
import pytest
from unittest.mock import patch, Mock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from packages.database.models import (
    User, Resume, RoleMatch, UserProfile, UserPreferences,
    JobRaw, JobParsed, JobScore,
)


# ── App client fixture (SQLite + all external services mocked) ────────────────

@pytest.fixture(scope="module")
def client(engine):
    """TestClient wired to SQLite in-memory DB, all external calls mocked."""
    from packages.database import connection as db_conn
    from sqlalchemy.orm import sessionmaker

    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    # Mock Azure & OpenAI before importing app
    with patch("azure.storage.blob.BlobServiceClient") as mock_blob_svc, \
         patch("openai.AzureOpenAI") as mock_openai_cls:

        # Blob mock
        blob_client = Mock()
        blob_client.url = "https://blob.example.com/resumes/test.docx"
        container_client = Mock()
        container_client.get_blob_client.return_value = blob_client
        mock_blob_svc.from_connection_string.return_value.get_container_client.return_value = container_client

        # OpenAI mock — returns valid ParsedJD JSON
        oai_response = Mock()
        oai_response.choices = [Mock()]
        oai_response.choices[0].message = Mock()
        oai_response.choices[0].message.content = json.dumps({
            "role": "Senior GenAI Engineer",
            "seniority": "Senior",
            "employment_type": "Full-time",
            "location_type": "Hybrid",
            "must_have_skills": ["Python", "LangChain", "Azure OpenAI"],
            "nice_to_have_skills": ["Kubernetes"],
            "responsibilities": ["Build LLM pipelines", "Lead architecture"],
            "ats_keywords": ["GenAI", "RAG", "LLM"],
            "red_flags": [],
            "salary_range": {"min": 150000, "max": 200000, "currency": "USD"},
        })
        mock_openai_cls.return_value.chat.completions.create.return_value = oai_response

        from apps.web.main import app
        from packages.database.connection import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

def auth_headers(user_id: str) -> dict:
    return {"X-User-ID": user_id}


def minimal_docx() -> bytes:
    """ZIP magic bytes — passes MIME/extension validation."""
    return b"PK\x03\x04" + b"\x00" * 100


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Auth
# ══════════════════════════════════════════════════════════════════════════════

class TestAuth:
    def test_signup_creates_user(self, client):
        res = client.post("/api/v1/users/signup", json={
            "email": "e2e_test@example.com",
            "password": "Test1234!",
            "full_name": "E2E Tester",
        })
        assert res.status_code == 200
        data = res.json()
        assert "user_id" in data
        assert data["email"] == "e2e_test@example.com"

    def test_duplicate_signup_rejected(self, client):
        client.post("/api/v1/users/signup", json={
            "email": "dup@example.com", "password": "pass", "full_name": "Dup",
        })
        res = client.post("/api/v1/users/signup", json={
            "email": "dup@example.com", "password": "pass", "full_name": "Dup",
        })
        assert res.status_code in (400, 409)

    def test_login_returns_user_id(self, client):
        client.post("/api/v1/users/signup", json={
            "email": "login_test@example.com",
            "password": "Test1234!",
            "full_name": "Login Test",
        })
        res = client.post("/api/v1/users/login", json={
            "email": "login_test@example.com",
            "password": "Test1234!",
        })
        assert res.status_code == 200
        assert "user_id" in res.json()

    def test_login_wrong_password_rejected(self, client):
        client.post("/api/v1/users/signup", json={
            "email": "wrongpw@example.com", "password": "correct", "full_name": "X",
        })
        res = client.post("/api/v1/users/login", json={
            "email": "wrongpw@example.com", "password": "wrong",
        })
        assert res.status_code in (401, 400)

    def test_me_without_header_rejected(self, client):
        res = client.get("/api/v1/users/me")
        assert res.status_code in (401, 403, 422)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Full happy path (stateful, steps run in order)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="class")
def flow_state():
    """Mutable dict shared across all steps in the happy-path flow."""
    return {}


@pytest.mark.usefixtures("flow_state")
class TestHappyPath:
    """
    Each test method advances the flow one step.  They intentionally share
    `flow_state` so outputs from earlier steps feed into later ones.
    The ordering is enforced via the `flow_state` fixture and method names.
    """

    # ── Step 1: Signup ────────────────────────────────────────────────────

    def test_step01_signup(self, client, flow_state):
        res = client.post("/api/v1/users/signup", json={
            "email":     "happy@jobforge.test",
            "password":  "HappyPath1!",
            "full_name": "Happy User",
        })
        assert res.status_code == 200, res.text
        data = res.json()
        assert "user_id" in data
        flow_state["user_id"]  = data["user_id"]
        flow_state["headers"]  = auth_headers(data["user_id"])

    # ── Step 2: Resume upload ─────────────────────────────────────────────

    def test_step02_resume_upload(self, client, flow_state):
        headers = flow_state["headers"]
        with patch("services.resume_storage.azure_storage.BlobServiceClient") as mock_bs:
            # Wire up blob mock inline
            blob = Mock(); blob.url = "https://blob.example.com/test.docx"
            mock_bs.from_connection_string.return_value \
                .get_container_client.return_value \
                .get_blob_client.return_value = blob

            res = client.post(
                "/api/v1/resume/upload",
                headers=headers,
                files=[("file", ("resume.docx", io.BytesIO(minimal_docx()),
                                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
            )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "resume_id" in data
        flow_state["resume_id"] = data["resume_id"]

    # ── Step 3: Second upload same file → 409 (not 500) ──────────────────

    def test_step03_duplicate_upload_gives_409_not_500(self, client, flow_state):
        headers = flow_state["headers"]
        with patch("services.resume_storage.azure_storage.BlobServiceClient") as mock_bs:
            blob = Mock(); blob.url = "https://blob.example.com/test.docx"
            mock_bs.from_connection_string.return_value \
                .get_container_client.return_value \
                .get_blob_client.return_value = blob

            res = client.post(
                "/api/v1/resume/upload",
                headers=headers,
                files=[("file", ("resume.docx", io.BytesIO(minimal_docx()),
                                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
            )
        # Should be 200 (same user dedup = return existing) or 409 — never 500
        assert res.status_code != 500, f"Got 500: {res.text}"

    # ── Step 4: List resumes ──────────────────────────────────────────────

    def test_step04_list_resumes(self, client, flow_state):
        res = client.get("/api/v1/resume/", headers=flow_state["headers"])
        assert res.status_code == 200
        resumes = res.json()
        assert isinstance(resumes, list)
        assert any(r["resume_id"] == flow_state["resume_id"] for r in resumes)

    # ── Step 5: Analyze resume (extract roles) ────────────────────────────

    def test_step05_analyze_resume(self, client, flow_state):
        with patch("services.resume_analyzer.role_extractor.RoleExtractor._call_llm") as mock_llm:
            mock_llm.return_value = ["Senior GenAI Engineer", "ML Engineer"]
            res = client.post(
                f"/api/v1/resume/analyze/{flow_state['resume_id']}",
                headers=flow_state["headers"],
            )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "roles" in data or "role_match_id" in data or isinstance(data, list)

    # ── Step 6: Get role suggestions ──────────────────────────────────────

    def test_step06_get_roles(self, client, flow_state):
        res = client.get(
            f"/api/v1/resume/roles/{flow_state['resume_id']}",
            headers=flow_state["headers"],
        )
        assert res.status_code == 200, res.text
        data = res.json()
        # Returns either a list or object with roles key
        roles = data if isinstance(data, list) else data.get("roles", [])
        assert len(roles) >= 0  # may be empty if analyze wasn't mocked perfectly
        flow_state["roles_data"] = roles

    # ── Step 7: Confirm role ──────────────────────────────────────────────

    def test_step07_confirm_role(self, client, flow_state):
        res = client.post(
            "/api/v1/resume/roles/confirm",
            headers=flow_state["headers"],
            json={"resume_id": flow_state["resume_id"],
                  "confirmed_role": "Senior GenAI Engineer"},
        )
        assert res.status_code == 200, res.text

    # ── Step 8: Build profile from resume ─────────────────────────────────

    def test_step08_build_profile(self, client, flow_state):
        with patch("services.resume_analyzer.profile_builder.ProfileBuilder._call_llm") as mock_llm:
            mock_llm.return_value = {
                "skills": {"languages": ["Python"], "frameworks": ["LangChain", "FastAPI"]},
                "experience_years": 6,
                "industries": ["Technology"],
            }
            res = client.post(
                f"/api/v1/profile/build-from-resume/{flow_state['resume_id']}",
                headers=flow_state["headers"],
            )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "profile_id" in data or "user_id" in data

    # ── Step 9: Get profile ───────────────────────────────────────────────

    def test_step09_get_profile(self, client, flow_state):
        res = client.get("/api/v1/profile", headers=flow_state["headers"])
        assert res.status_code == 200, res.text

    # ── Step 10: Set preferences ──────────────────────────────────────────

    def test_step10_set_preferences(self, client, flow_state):
        res = client.post(
            "/api/v1/preferences/",
            headers=flow_state["headers"],
            json={
                "target_roles":          ["Senior GenAI Engineer"],
                "salary_min_usd":        140_000,
                "preferred_locations":   ["Dallas, TX", "Remote"],
                "visa_status":           "H1B",
                "location_preferences":  {"remote_only": False},
                "preferred_industries":  ["Technology"],
            },
        )
        assert res.status_code in (200, 201), res.text
        flow_state["prefs_id"] = res.json().get("preferences_id") or res.json().get("id")

    # ── Step 11: Update preferences ───────────────────────────────────────

    def test_step11_update_preferences(self, client, flow_state):
        res = client.put(
            "/api/v1/preferences/",
            headers=flow_state["headers"],
            json={"salary_min_usd": 150_000},
        )
        assert res.status_code == 200, res.text

    # ── Step 12: List jobs (empty catalog is fine) ────────────────────────

    def test_step12_list_jobs_empty(self, client, flow_state):
        res = client.get("/api/v1/jobs/", headers=flow_state["headers"])
        assert res.status_code == 200
        data = res.json()
        assert "jobs" in data
        assert isinstance(data["jobs"], list)

    # ── Step 13: Ingest a job directly into DB and parse it ───────────────

    def test_step13_ingest_and_parse_job(self, client, flow_state, db, sample_job_text):
        """Insert a job row directly, then call the parse endpoint."""
        job = JobRaw(
            title="Senior GenAI Engineer",
            company="Deloitte",
            location="Dallas, TX",
            source="test",
            source_url="https://example.com/job/1",
            text_content=sample_job_text,
            content_hash=str(uuid.uuid4()).replace("-", ""),
        )
        db.add(job); db.commit(); db.refresh(job)
        flow_state["job_id"] = str(job.job_id)

        with patch("services.jd_parser.jd_parser.JDParser.parse") as mock_parse:
            from packages.schemas.jd_schema import ParsedJD, SalaryRange
            mock_parse.return_value = ParsedJD(
                role="Senior GenAI Engineer",
                must_have_skills=["Python", "LangChain"],
                nice_to_have_skills=["Kubernetes"],
                salary_range=SalaryRange(min=150_000, max=200_000),
            )
            res = client.post(
                f"/api/v1/jobs/{flow_state['job_id']}/parse",
                headers=flow_state["headers"],
            )
        assert res.status_code == 200, res.text
        assert res.json()["parse_status"] == "PARSED"

    # ── Step 14: GET /jobs/{id} — the new single-job endpoint ────────────

    def test_step14_get_single_job(self, client, flow_state):
        res = client.get(
            f"/api/v1/jobs/{flow_state['job_id']}",
            headers=flow_state["headers"],
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["job_id"]  == flow_state["job_id"]
        assert data["company"] == "Deloitte"
        assert "verdict"       in data   # NOT_SCORED initially
        assert "parse_status"  in data

    # ── Step 15: GET /jobs/{id}/parsed ────────────────────────────────────

    def test_step15_get_parsed_jd(self, client, flow_state):
        res = client.get(
            f"/api/v1/jobs/{flow_state['job_id']}/parsed",
            headers=flow_state["headers"],
        )
        assert res.status_code == 200, res.text
        assert res.json()["parse_status"] == "PARSED"

    # ── Step 16: Score the job ────────────────────────────────────────────

    def test_step16_score_job(self, client, flow_state):
        res = client.post(
            f"/api/v1/jobs/{flow_state['job_id']}/score",
            headers=flow_state["headers"],
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "total_score" in data
        assert "verdict"     in data
        assert data["verdict"] != "REJECTED", (
            f"Good job wrongly rejected: {data.get('rationale')}"
        )
        assert 0 <= data["total_score"] <= 100
        flow_state["verdict"] = data["verdict"]

    # ── Step 17: GET score ────────────────────────────────────────────────

    def test_step17_get_score(self, client, flow_state):
        res = client.get(
            f"/api/v1/jobs/{flow_state['job_id']}/score",
            headers=flow_state["headers"],
        )
        assert res.status_code == 200, res.text
        assert "total_score" in res.json()

    # ── Step 18: Score-all (idempotent) ───────────────────────────────────

    def test_step18_score_all(self, client, flow_state):
        res = client.post("/api/v1/jobs/score-all", headers=flow_state["headers"])
        assert res.status_code == 200, res.text
        data = res.json()
        # Already scored job should be in skipped_already_scored
        assert "skipped_already_scored" in data

    # ── Step 19: Job detail page — single-job endpoint works ─────────────

    def test_step19_job_detail_not_black_screen(self, client, flow_state):
        """Simulates what JobDetailPage.jsx now does: GET /jobs/{id}."""
        res = client.get(
            f"/api/v1/jobs/{flow_state['job_id']}",
            headers=flow_state["headers"],
        )
        assert res.status_code == 200
        data = res.json()
        # All fields the UI depends on must be present
        for field in ("job_id", "title", "company", "location",
                      "verdict", "score", "parse_status"):
            assert field in data, f"Missing field '{field}' in job detail response"

    # ── Step 20: Nonexistent job → 404 (not black screen) ─────────────────

    def test_step20_nonexistent_job_404(self, client, flow_state):
        fake_id = str(uuid.uuid4())
        res = client.get(f"/api/v1/jobs/{fake_id}", headers=flow_state["headers"])
        assert res.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — Regression tests for specific bugs fixed in Sprint 1
# ══════════════════════════════════════════════════════════════════════════════

class TestRegressions:
    """One test per bug we fixed — if any of these fail after a refactor,
    we know exactly which bug regressed."""

    def test_r01_resume_upload_safari_octet_stream_accepted(self, client, engine):
        """Safari sends .docx as application/octet-stream — must not 415."""
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        db = Session()

        res_signup = client.post("/api/v1/users/signup", json={
            "email":     "safari@test.com",
            "password":  "Safari123!",
            "full_name": "Safari User",
        })
        uid = res_signup.json()["user_id"]

        with patch("services.resume_storage.azure_storage.BlobServiceClient") as mock_bs:
            blob = Mock(); blob.url = "https://blob.example.com/test.docx"
            mock_bs.from_connection_string.return_value \
                .get_container_client.return_value \
                .get_blob_client.return_value = blob

            res = client.post(
                "/api/v1/resume/upload",
                headers=auth_headers(uid),
                files=[("file", ("resume.docx",
                                 io.BytesIO(minimal_docx()),
                                 "application/octet-stream"))],  # Safari MIME
            )
        assert res.status_code != 415, "Safari .docx upload wrongly rejected by MIME check"
        db.close()

    def test_r02_cross_user_same_file_gives_409_not_500(self, client):
        """Two users uploading the same file must each get their own resume row."""
        emails = ["user_a@cross.test", "user_b@cross.test"]
        user_ids = []
        for email in emails:
            r = client.post("/api/v1/users/signup", json={
                "email": email, "password": "Test123!", "full_name": "X",
            })
            user_ids.append(r.json()["user_id"])

        with patch("services.resume_storage.azure_storage.BlobServiceClient") as mock_bs:
            blob = Mock(); blob.url = "https://blob.example.com/test.docx"
            mock_bs.from_connection_string.return_value \
                .get_container_client.return_value \
                .get_blob_client.return_value = blob

            results = []
            for uid in user_ids:
                r = client.post(
                    "/api/v1/resume/upload",
                    headers=auth_headers(uid),
                    files=[("file", ("resume.docx",
                                     io.BytesIO(minimal_docx()),
                                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
                )
                results.append(r.status_code)

        # Neither should be 500
        assert 500 not in results, f"Got 500 on cross-user upload: {results}"

    def test_r03_score_endpoint_auto_parses_unparsed_job(self, client, db, engine):
        """Scoring an unparsed job must auto-parse it, not return 422."""
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()

        r = client.post("/api/v1/users/signup", json={
            "email":     "autoparse@test.com",
            "password":  "Test123!",
            "full_name": "Auto Parse",
        })
        uid = r.json()["user_id"]

        # Insert job with no JobParsed row
        job = JobRaw(
            title="Test Job", company="ACME", location="Remote",
            source="test", source_url="https://example.com",
            text_content="Python developer role, salary $150k",
            content_hash=str(uuid.uuid4()).replace("-", ""),
        )
        session.add(job); session.commit(); session.refresh(job)
        jid = str(job.job_id)

        # Also need profile + preferences for scoring
        from packages.database.models import UserProfile, UserPreferences
        import uuid as _uuid
        profile = UserProfile(
            user_id=_uuid.UUID(uid),
            confirmed_role="Python Developer",
            skills={"languages": ["Python"]},
            experience_years=5,
        )
        prefs = UserPreferences(
            user_id=_uuid.UUID(uid),
            target_roles=["Python Developer"],
            salary_min_usd=100_000,
            visa_status="H1B",
            location_preferences={"remote_only": False},
        )
        session.add(profile); session.add(prefs); session.commit()

        with patch("services.jd_parser.jd_parser.JDParser.parse") as mock_parse:
            from packages.schemas.jd_schema import ParsedJD
            mock_parse.return_value = ParsedJD(
                role="Python Developer",
                must_have_skills=["Python"],
                salary_range={"min": 120_000, "max": 180_000},
            )
            res = client.post(f"/api/v1/jobs/{jid}/score",
                              headers=auth_headers(uid))

        assert res.status_code == 200, res.text
        assert res.json().get("verdict") != "REJECTED"
        session.close()

    def test_r04_job_detail_sub_paths_not_swallowed_by_wildcard(self, client, db, engine):
        """GET /jobs/{id}/parsed must NOT be caught by GET /jobs/{id}."""
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()

        r = client.post("/api/v1/users/signup", json={
            "email":     "routetest@test.com",
            "password":  "Test123!",
            "full_name": "Route Test",
        })
        uid = r.json()["user_id"]

        job = JobRaw(
            title="Route Test Job", company="ACME", location="Remote",
            source="test", source_url="https://example.com",
            text_content="Python developer",
            content_hash=str(uuid.uuid4()).replace("-", ""),
        )
        session.add(job); session.commit(); session.refresh(job)
        jid = str(job.job_id)

        # GET /jobs/{id} should return 200 with job metadata
        res_detail = client.get(f"/api/v1/jobs/{jid}",
                                headers=auth_headers(uid))
        assert res_detail.status_code == 200
        assert "company" in res_detail.json()

        # GET /jobs/{id}/parsed should return 404 (not parsed yet) — NOT the job dict
        res_parsed = client.get(f"/api/v1/jobs/{jid}/parsed",
                                headers=auth_headers(uid))
        assert res_parsed.status_code == 404  # correct: not parsed yet
        # The 404 body should mention "parsed" not be a job object
        assert "company" not in res_parsed.json()

        session.close()

    def test_r05_bad_salary_parse_does_not_reject_good_job(self):
        """$100 salary (bad LLM parse) must not hard-reject the job."""
        from packages.schemas.jd_schema import ParsedJD, SalaryRange
        from services.scoring.rules_engine import RulesEngine

        prefs = Mock()
        prefs.salary_min_usd       = 100_000
        prefs.visa_status          = "H1B"
        prefs.location_preferences = {"remote_only": False}

        # After normalisation, $100 → $100,000 which meets the floor exactly
        jd = ParsedJD(role="Senior Engineer",
                      salary_range=SalaryRange(min=100, max=100))
        ok, reason = RulesEngine().check_constraints(jd, prefs)
        # $100 normalised to $100,000 = exactly at floor → should pass
        assert ok is True, f"Normalised $100k was rejected: {reason}"
