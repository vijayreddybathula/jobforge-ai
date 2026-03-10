"""End-to-end happy path tests.

All external I/O (Azure Blob, Azure OpenAI) is mocked.
The database uses the shared SQLite in-memory engine from conftest.py.

Design notes
------------
* TestAuth  — independent tests, each creates its own user.
* TestHappyPath — sequential 20-step flow sharing `flow_state`.
  Steps are isolated from TestAuth via a separate user email.
* TestRegressions — independent regression tests for each bug class.
"""

import io
import uuid
import json
import pytest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def auth_headers(user_id: str) -> dict:
    return {"X-User-ID": str(user_id)}


def minimal_docx() -> bytes:
    """ZIP magic bytes — passes MIME/extension check."""
    return b"PK\x03\x04" + b"\x00" * 100


def _blob_patch():
    """Context manager that mocks Azure Blob storage."""
    blob = Mock()
    blob.url = "https://blob.example.com/test.docx"
    svc  = Mock()
    svc.get_container_client.return_value.get_blob_client.return_value = blob
    return patch(
        "azure.storage.blob.BlobServiceClient.from_connection_string",
        return_value=svc,
    )


_PARSED_JD_JSON = json.dumps({
    "role": "Senior GenAI Engineer", "seniority": "Senior",
    "employment_type": "Full-time", "location_type": "Hybrid",
    "must_have_skills": ["Python", "LangChain", "Azure OpenAI"],
    "nice_to_have_skills": ["Kubernetes"],
    "responsibilities": ["Build LLM pipelines", "Lead architecture"],
    "ats_keywords": ["GenAI", "RAG", "LLM"],
    "red_flags": [],
    "salary_range": {"min": 150000, "max": 200000, "currency": "USD"},
})

_ROLE_EXTRACT_JSON = json.dumps({
    "current_role": "Senior GenAI Engineer",
    "years_of_experience": 6,
    "core_skills": ["Python", "LangChain"],
    "technologies": ["Azure OpenAI"],
    "industry_domain": "Technology",
    "seniority_level": "Senior",
    "suggested_roles": [
        {"role_title": "Senior GenAI Engineer",
         "confidence_score": 95,
         "reasoning": "Exact match"}
    ],
})


# ---------------------------------------------------------------------------
# Shared TestClient (module-scoped; wired to SQLite via SessionFactory)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client(engine, SessionFactory):
    from packages.database.connection import get_db
    from apps.web.main import app

    def override_get_db():
        s = SessionFactory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db

    oai_response = Mock()
    oai_response.choices = [Mock()]
    oai_response.choices[0].message = Mock()
    oai_response.choices[0].message.content = _PARSED_JD_JSON

    with patch("openai.AzureOpenAI") as mock_oai:
        mock_oai.return_value.chat.completions.create.return_value = oai_response
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    app.dependency_overrides.clear()


# ===========================================================================
# PHASE 1 — Auth (independent)
# ===========================================================================

class TestAuth:
    def test_signup_creates_user(self, client):
        res = client.post("/api/v1/users/signup", json={
            "email": f"auth_test_{uuid.uuid4().hex[:6]}@example.com",
            "password": "Test1234!", "full_name": "Auth Test",
        })
        assert res.status_code == 200, res.text
        assert "user_id" in res.json()

    def test_duplicate_signup_rejected(self, client):
        email = f"dup_{uuid.uuid4().hex[:6]}@example.com"
        client.post("/api/v1/users/signup",
                    json={"email": email, "password": "pass", "full_name": "Dup"})
        res = client.post("/api/v1/users/signup",
                          json={"email": email, "password": "pass", "full_name": "Dup"})
        assert res.status_code in (400, 409), res.text

    def test_login_returns_user_id(self, client):
        email = f"login_{uuid.uuid4().hex[:6]}@example.com"
        client.post("/api/v1/users/signup",
                    json={"email": email, "password": "Test1234!", "full_name": "Login"})
        res = client.post("/api/v1/users/login",
                          json={"email": email, "password": "Test1234!"})
        assert res.status_code == 200, res.text
        assert "user_id" in res.json()

    def test_login_wrong_password_rejected(self, client):
        email = f"wrongpw_{uuid.uuid4().hex[:6]}@example.com"
        client.post("/api/v1/users/signup",
                    json={"email": email, "password": "correct", "full_name": "X"})
        res = client.post("/api/v1/users/login",
                          json={"email": email, "password": "wrong"})
        assert res.status_code in (400, 401), res.text

    def test_me_without_header_rejected(self, client):
        res = client.get("/api/v1/users/me")
        assert res.status_code in (401, 403, 422), res.text


# ===========================================================================
# PHASE 2 — Happy path (sequential, shared flow_state)
# ===========================================================================

@pytest.fixture(scope="class")
def flow_state():
    return {}


@pytest.mark.usefixtures("flow_state")
class TestHappyPath:

    # Step 1 — signup
    def test_step01_signup(self, client, flow_state):
        res = client.post("/api/v1/users/signup", json={
            "email": f"happy_{uuid.uuid4().hex[:6]}@jobforge.test",
            "password": "HappyPath1!", "full_name": "Happy User",
        })
        assert res.status_code == 200, res.text
        data = res.json()
        assert "user_id" in data
        flow_state["user_id"] = data["user_id"]
        flow_state["headers"] = auth_headers(data["user_id"])

    # Step 2 — resume upload
    def test_step02_resume_upload(self, client, flow_state):
        headers = flow_state["headers"]
        with _blob_patch():
            res = client.post(
                "/api/v1/resume/upload", headers=headers,
                files=[("file", ("resume.docx", io.BytesIO(minimal_docx()),
                                 "application/vnd.openxmlformats-officedocument"
                                 ".wordprocessingml.document"))],
            )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "resume_id" in data
        flow_state["resume_id"] = data["resume_id"]

    # Step 3 — duplicate upload must not 500
    def test_step03_duplicate_upload_no_500(self, client, flow_state):
        with _blob_patch():
            res = client.post(
                "/api/v1/resume/upload", headers=flow_state["headers"],
                files=[("file", ("resume.docx", io.BytesIO(minimal_docx()),
                                 "application/vnd.openxmlformats-officedocument"
                                 ".wordprocessingml.document"))],
            )
        assert res.status_code != 500, f"Duplicate upload returned 500: {res.text}"

    # Step 4 — list resumes
    def test_step04_list_resumes(self, client, flow_state):
        res = client.get("/api/v1/resume/", headers=flow_state["headers"])
        assert res.status_code == 200, res.text
        resumes = res.json()
        assert any(r["resume_id"] == flow_state["resume_id"] for r in resumes)

    # Step 5 — analyze resume
    def test_step05_analyze_resume(self, client, flow_state):
        oai = Mock()
        oai.choices = [Mock()]
        oai.choices[0].message = Mock()
        oai.choices[0].message.content = _ROLE_EXTRACT_JSON
        with patch("openai.AzureOpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = oai
            res = client.post(
                f"/api/v1/resume/analyze/{flow_state['resume_id']}",
                headers=flow_state["headers"],
            )
        assert res.status_code == 200, res.text

    # Step 6 — get roles
    def test_step06_get_roles(self, client, flow_state):
        res = client.get(
            f"/api/v1/resume/roles/{flow_state['resume_id']}",
            headers=flow_state["headers"],
        )
        assert res.status_code == 200, res.text

    # Step 7 — confirm role
    def test_step07_confirm_role(self, client, flow_state):
        res = client.post(
            "/api/v1/resume/roles/confirm", headers=flow_state["headers"],
            json={"resume_id": flow_state["resume_id"],
                  "confirmed_role": "Senior GenAI Engineer"},
        )
        assert res.status_code == 200, res.text

    # Step 8 — build profile
    def test_step08_build_profile(self, client, flow_state):
        oai = Mock()
        oai.choices = [Mock()]
        oai.choices[0].message = Mock()
        oai.choices[0].message.content = _ROLE_EXTRACT_JSON
        with patch("openai.AzureOpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.return_value = oai
            res = client.post(
                f"/api/v1/profile/build-from-resume/{flow_state['resume_id']}",
                headers=flow_state["headers"],
            )
        assert res.status_code == 200, res.text

    # Step 9 — get profile
    def test_step09_get_profile(self, client, flow_state):
        res = client.get("/api/v1/profile", headers=flow_state["headers"])
        assert res.status_code == 200, res.text

    # Step 10 — set preferences
    def test_step10_set_preferences(self, client, flow_state):
        res = client.post("/api/v1/preferences/", headers=flow_state["headers"], json={
            "target_roles": ["Senior GenAI Engineer"],
            "salary_min_usd": 140_000,
            "preferred_locations": ["Dallas, TX"],
            "visa_status": "H1B",
            "location_preferences": {"remote_only": False},
            "preferred_industries": ["Technology"],
        })
        assert res.status_code in (200, 201), res.text

    # Step 11 — update preferences
    def test_step11_update_preferences(self, client, flow_state):
        res = client.put("/api/v1/preferences/", headers=flow_state["headers"],
                         json={"salary_min_usd": 150_000})
        assert res.status_code == 200, res.text

    # Step 12 — list jobs (empty catalog is fine)
    def test_step12_list_jobs_empty(self, client, flow_state):
        res = client.get("/api/v1/jobs/", headers=flow_state["headers"])
        assert res.status_code == 200, res.text
        assert "jobs" in res.json()

    # Step 13 — ingest a job via the API parse-all trigger
    def test_step13_ingest_job_directly(self, client, flow_state, SessionFactory, sample_job_text):
        from packages.database.models import JobRaw
        session = SessionFactory()
        job = JobRaw(
            title="Senior GenAI Engineer", company="Deloitte",
            location="Dallas, TX", source="test",
            source_url=f"https://example.com/job/{uuid.uuid4().hex}",
            text_content=sample_job_text,
            content_hash=uuid.uuid4().hex,
        )
        session.add(job)
        session.commit()
        flow_state["job_id"] = str(job.job_id)
        session.close()

    # Step 14 — parse the job
    def test_step14_parse_job(self, client, flow_state):
        from packages.schemas.jd_schema import ParsedJD, SalaryRange
        mock_jd = ParsedJD(
            role="Senior GenAI Engineer",
            must_have_skills=["Python", "LangChain"],
            salary_range=SalaryRange(min=150_000, max=200_000),
        )
        with patch("services.jd_parser.jd_parser.JDParser.parse",
                   return_value=mock_jd):
            res = client.post(
                f"/api/v1/jobs/{flow_state['job_id']}/parse",
                headers=flow_state["headers"],
            )
        assert res.status_code == 200, res.text
        assert res.json()["parse_status"] == "PARSED"

    # Step 15 — GET /jobs/{id} — single job endpoint
    def test_step15_get_single_job(self, client, flow_state):
        res = client.get(
            f"/api/v1/jobs/{flow_state['job_id']}",
            headers=flow_state["headers"],
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["job_id"]  == flow_state["job_id"]
        assert data["company"] == "Deloitte"
        assert "verdict" in data

    # Step 16 — GET /jobs/{id}/parsed — must NOT be swallowed by wildcard
    def test_step16_get_parsed_jd(self, client, flow_state):
        res = client.get(
            f"/api/v1/jobs/{flow_state['job_id']}/parsed",
            headers=flow_state["headers"],
        )
        assert res.status_code == 200, res.text
        assert res.json()["parse_status"] == "PARSED"

    # Step 17 — score the job
    def test_step17_score_job(self, client, flow_state):
        from packages.schemas.jd_schema import ParsedJD, SalaryRange
        mock_jd = ParsedJD(
            role="Senior GenAI Engineer",
            must_have_skills=["Python", "LangChain"],
            salary_range=SalaryRange(min=150_000, max=200_000),
        )
        with patch("services.jd_parser.jd_parser.JDParser.parse",
                   return_value=mock_jd):
            res = client.post(
                f"/api/v1/jobs/{flow_state['job_id']}/score",
                headers=flow_state["headers"],
            )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "total_score" in data
        assert "verdict" in data
        assert data["verdict"] != "REJECTED", f"Wrongly rejected: {data.get('rationale')}"
        assert 0 <= data["total_score"] <= 100

    # Step 18 — GET score
    def test_step18_get_score(self, client, flow_state):
        res = client.get(
            f"/api/v1/jobs/{flow_state['job_id']}/score",
            headers=flow_state["headers"],
        )
        assert res.status_code == 200, res.text
        assert "total_score" in res.json()

    # Step 19 — score-all (idempotent)
    def test_step19_score_all(self, client, flow_state):
        res = client.post("/api/v1/jobs/score-all",
                          headers=flow_state["headers"])
        assert res.status_code == 200, res.text
        assert "skipped_already_scored" in res.json()

    # Step 20 — job detail page fields check
    def test_step20_job_detail_fields(self, client, flow_state):
        res = client.get(
            f"/api/v1/jobs/{flow_state['job_id']}",
            headers=flow_state["headers"],
        )
        assert res.status_code == 200
        data = res.json()
        for field in ("job_id", "title", "company", "location",
                      "verdict", "score", "parse_status"):
            assert field in data, f"Missing field '{field}'"

    # Step 21 — nonexistent job → 404
    def test_step21_nonexistent_job_404(self, client, flow_state):
        fake = str(uuid.uuid4())
        res = client.get(f"/api/v1/jobs/{fake}",
                         headers=flow_state["headers"])
        assert res.status_code == 404


# ===========================================================================
# PHASE 3 — Regression tests (one per bug fixed in Sprint 1)
# ===========================================================================

class TestRegressions:

    def test_r01_safari_octet_stream_upload_not_rejected(self, client):
        """Safari sends .docx as application/octet-stream — must not 415."""
        res = client.post("/api/v1/users/signup", json={
            "email": f"safari_{uuid.uuid4().hex[:6]}@test.com",
            "password": "Safari123!", "full_name": "Safari",
        })
        uid = res.json()["user_id"]
        with _blob_patch():
            res = client.post(
                "/api/v1/resume/upload", headers=auth_headers(uid),
                files=[("file", ("resume.docx", io.BytesIO(minimal_docx()),
                                 "application/octet-stream"))],
            )
        assert res.status_code != 415, "Safari .docx wrongly rejected"

    def test_r02_cross_user_same_file_no_500(self, client):
        """Two users uploading identical bytes must not produce a 500."""
        uids = []
        for i in range(2):
            r = client.post("/api/v1/users/signup", json={
                "email": f"cross_{i}_{uuid.uuid4().hex[:6]}@test.com",
                "password": "Test123!", "full_name": "X",
            })
            uids.append(r.json()["user_id"])

        # Use SAME bytes for both users
        same_bytes = minimal_docx()
        results = []
        with _blob_patch():
            for uid in uids:
                r = client.post(
                    "/api/v1/resume/upload", headers=auth_headers(uid),
                    files=[("file", ("resume.docx", io.BytesIO(same_bytes),
                                     "application/vnd.openxmlformats-officedocument"
                                     ".wordprocessingml.document"))],
                )
                results.append(r.status_code)
        assert 500 not in results, f"Got 500 on cross-user upload: {results}"

    def test_r03_score_auto_parses_unparsed_job(self, client, SessionFactory):
        """Scoring an unparsed job must auto-parse it, not return 422."""
        r = client.post("/api/v1/users/signup", json={
            "email": f"autoparse_{uuid.uuid4().hex[:6]}@test.com",
            "password": "Test123!", "full_name": "AP",
        })
        uid = r.json()["user_id"]

        from packages.database.models import JobRaw, UserProfile, UserPreferences
        session = SessionFactory()
        job = JobRaw(
            title="Test", company="ACME", location="Remote",
            source="test",
            source_url=f"https://example.com/{uuid.uuid4().hex}",
            text_content="Python developer, salary $150k",
            content_hash=uuid.uuid4().hex,
        )
        profile = UserProfile(
            user_id=uid,
            confirmed_role="Python Developer",
            skills={"languages": ["Python"]},
            experience_years=5,
        )
        prefs = UserPreferences(
            user_id=uid,
            target_roles=["Python Developer"],
            salary_min_usd=100_000,
            visa_status="H1B",
            location_preferences={"remote_only": False},
        )
        session.add_all([job, profile, prefs])
        session.commit()
        jid = str(job.job_id)
        session.close()

        from packages.schemas.jd_schema import ParsedJD
        mock_jd = ParsedJD(role="Python Developer",
                           must_have_skills=["Python"],
                           salary_range={"min": 120_000, "max": 180_000})
        with patch("services.jd_parser.jd_parser.JDParser.parse",
                   return_value=mock_jd):
            res = client.post(f"/api/v1/jobs/{jid}/score",
                              headers=auth_headers(uid))
        assert res.status_code == 200, res.text
        assert res.json().get("verdict") != "REJECTED"

    def test_r04_wildcard_does_not_swallow_sub_paths(self, client, SessionFactory):
        """GET /jobs/{id}/parsed must NOT be caught by GET /jobs/{id}."""
        r = client.post("/api/v1/users/signup", json={
            "email": f"route_{uuid.uuid4().hex[:6]}@test.com",
            "password": "Test123!", "full_name": "RT",
        })
        uid = r.json()["user_id"]

        from packages.database.models import JobRaw
        session = SessionFactory()
        job = JobRaw(
            title="Route Test", company="ACME", location="Remote",
            source="test",
            source_url=f"https://example.com/{uuid.uuid4().hex}",
            text_content="Python developer",
            content_hash=uuid.uuid4().hex,
        )
        session.add(job); session.commit()
        jid = str(job.job_id)
        session.close()

        # GET /jobs/{id} → 200 with job metadata
        res = client.get(f"/api/v1/jobs/{jid}", headers=auth_headers(uid))
        assert res.status_code == 200
        assert "company" in res.json()

        # GET /jobs/{id}/parsed → 404 (not parsed), NOT the job dict
        res = client.get(f"/api/v1/jobs/{jid}/parsed", headers=auth_headers(uid))
        assert res.status_code == 404
        assert "company" not in res.json()

    def test_r05_bad_salary_parse_does_not_reject_good_job(self):
        """$100 (bad LLM parse) normalises to $100k and must not hard-reject."""
        from packages.schemas.jd_schema import ParsedJD, SalaryRange
        from services.scoring.rules_engine import RulesEngine
        from unittest.mock import Mock

        prefs = Mock()
        prefs.salary_min_usd       = 100_000
        prefs.visa_status          = "H1B"
        prefs.location_preferences = {"remote_only": False}

        # $100 → normalised to $100,000 by SalaryRange validator
        jd = ParsedJD(role="Senior Engineer",
                      salary_range=SalaryRange(min=100, max=100))
        ok, reason = RulesEngine().check_constraints(jd, prefs)
        assert ok is True, f"Normalised $100k was wrongly rejected: {reason}"
