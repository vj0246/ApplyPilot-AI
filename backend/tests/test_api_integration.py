"""
Integration tests — hit real FastAPI routes against a real Postgres DB.

BEFORE RUNNING:
  docker compose up -d db
  export TEST_DATABASE_URL=postgresql+asyncpg://applypilot:applypilot@localhost:5432/applypilot

  pytest tests/test_api_integration.py -v

These are deliberately skipped when TEST_DATABASE_URL isn't set so CI
doesn't need Postgres unless you explicitly configure it.
"""
import os
import uuid
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ,
    reason="Set TEST_DATABASE_URL to run integration tests (needs real Postgres)"
)

# patch DATABASE_URL before importing main
os.environ.setdefault("DATABASE_URL", os.environ.get("TEST_DATABASE_URL", ""))
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-integration-32ch")
os.environ.setdefault("GROQ_API_KEY", "gsk_test")

import main  # noqa: E402
client = TestClient(main.app)


# ── helpers ──────────────────────────────────────────────────────────────

def register_and_login(email: str = None, password: str = "TestPass123!") -> dict:
    """Create a user and return {token, user_id, headers}."""
    email = email or f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "full_name": "Test User"
    })
    assert r.status_code == 201, f"Register failed: {r.text}"
    data = r.json()
    token = data["access_token"]
    return {
        "token": token,
        "user_id": data["user"]["id"],
        "headers": {"Authorization": f"Bearer {token}"},
    }


# ── auth ─────────────────────────────────────────────────────────────────

class TestAuth:
    def test_register_success(self):
        r = client.post("/api/v1/auth/register", json={
            "email": f"u_{uuid.uuid4().hex[:8]}@x.com",
            "password": "StrongPass123!", "full_name": "Test"
        })
        assert r.status_code == 201
        assert "access_token" in r.json()

    def test_register_duplicate_email_returns_409(self):
        email = f"dup_{uuid.uuid4().hex[:8]}@x.com"
        payload = {"email": email, "password": "StrongPass123!", "full_name": "T"}
        client.post("/api/v1/auth/register", json=payload)
        r = client.post("/api/v1/auth/register", json=payload)
        assert r.status_code == 409

    def test_register_short_password_returns_422(self):
        r = client.post("/api/v1/auth/register", json={
            "email": "x@y.com", "password": "short", "full_name": "T"
        })
        assert r.status_code == 422

    def test_login_success(self):
        email = f"login_{uuid.uuid4().hex[:8]}@x.com"
        client.post("/api/v1/auth/register", json={
            "email": email, "password": "StrongPass123!", "full_name": "T"
        })
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123!"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_login_wrong_password_returns_401(self):
        email = f"wp_{uuid.uuid4().hex[:8]}@x.com"
        client.post("/api/v1/auth/register", json={
            "email": email, "password": "StrongPass123!", "full_name": "T"
        })
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword!"})
        assert r.status_code == 401

    def test_me_requires_auth(self):
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401

    def test_me_returns_user(self):
        u = register_and_login()
        r = client.get("/api/v1/auth/me", headers=u["headers"])
        assert r.status_code == 200
        assert r.json()["id"] == u["user_id"]


# ── resumes ───────────────────────────────────────────────────────────────

class TestResumes:
    def test_list_empty_initially(self):
        u = register_and_login()
        r = client.get("/api/v1/resumes/", headers=u["headers"])
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_upload_invalid_type_returns_415(self):
        u = register_and_login()
        r = client.post("/api/v1/resumes/upload", headers=u["headers"],
                        files={"file": ("photo.jpg", b"fake-jpeg", "image/jpeg")})
        assert r.status_code == 415

    def test_upload_empty_file_returns_422(self):
        u = register_and_login()
        r = client.post("/api/v1/resumes/upload", headers=u["headers"],
                        files={"file": ("r.pdf", b"x", "application/pdf")})
        assert r.status_code == 422

    def test_upload_pdf_returns_202(self):
        u = register_and_login()
        # minimal but valid-looking PDF header so file size check passes
        pdf = b"%PDF-1.4 " + b"x" * 200
        r = client.post("/api/v1/resumes/upload", headers=u["headers"],
                        files={"file": ("resume.pdf", pdf, "application/pdf")})
        assert r.status_code == 202
        assert "id" in r.json()

    def test_upload_requires_auth(self):
        r = client.post("/api/v1/resumes/upload",
                        files={"file": ("r.pdf", b"%PDF" + b"x"*200, "application/pdf")})
        assert r.status_code == 401

    def test_get_nonexistent_returns_404(self):
        u = register_and_login()
        r = client.get(f"/api/v1/resumes/{uuid.uuid4()}", headers=u["headers"])
        assert r.status_code == 404

    def test_cannot_access_other_users_resume(self):
        u1 = register_and_login()
        u2 = register_and_login()
        pdf = b"%PDF-1.4 " + b"x" * 200
        upload = client.post("/api/v1/resumes/upload", headers=u1["headers"],
                             files={"file": ("r.pdf", pdf, "application/pdf")})
        resume_id = upload.json()["id"]
        r = client.get(f"/api/v1/resumes/{resume_id}", headers=u2["headers"])
        assert r.status_code == 404


# ── jobs ──────────────────────────────────────────────────────────────────

class TestJobs:
    def test_create_job_with_text_returns_202(self):
        u = register_and_login()
        r = client.post("/api/v1/jobs/", headers=u["headers"],
                        json={"text": "Senior Python Engineer at Acme. " * 20})
        assert r.status_code == 202
        assert "id" in r.json()

    def test_create_job_requires_at_least_one_field(self):
        u = register_and_login()
        r = client.post("/api/v1/jobs/", headers=u["headers"], json={})
        assert r.status_code == 422

    def test_list_jobs_empty(self):
        u = register_and_login()
        r = client.get("/api/v1/jobs/", headers=u["headers"])
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_delete_job(self):
        u = register_and_login()
        create = client.post("/api/v1/jobs/", headers=u["headers"],
                             json={"text": "Python Engineer at Acme. " * 20})
        job_id = create.json()["id"]
        r = client.delete(f"/api/v1/jobs/{job_id}", headers=u["headers"])
        assert r.status_code == 204

    def test_job_salary_currency_defaults_to_usd(self):
        u = register_and_login()
        r = client.post("/api/v1/jobs/", headers=u["headers"],
                        json={"title": "Eng", "company": "Co"})
        job_id = r.json()["id"]
        get = client.get(f"/api/v1/jobs/{job_id}", headers=u["headers"])
        # currency defaults to USD at the DB level
        assert get.json().get("salary_currency") == "USD"


# ── applications ──────────────────────────────────────────────────────────

class TestApplications:
    def test_generate_requires_ready_job(self):
        u = register_and_login()
        job = client.post("/api/v1/jobs/", headers=u["headers"],
                          json={"text": "Python Engineer " * 20}).json()
        pdf = b"%PDF-1.4 " + b"x" * 200
        resume = client.post("/api/v1/resumes/upload", headers=u["headers"],
                             files={"file": ("r.pdf", pdf, "application/pdf")}).json()
        # job is still "processing" — should reject with 409
        r = client.post("/api/v1/applications/generate", headers=u["headers"],
                        json={"job_id": job["id"], "resume_id": resume["id"]})
        assert r.status_code == 409

    def test_list_applications_empty(self):
        u = register_and_login()
        r = client.get("/api/v1/applications/", headers=u["headers"])
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_answer_questions_without_resume_returns_409(self):
        u = register_and_login()
        r = client.post("/api/v1/applications/answer-questions", headers=u["headers"],
                        json={"questions": ["Why do you want to work here?"]})
        assert r.status_code == 409


# ── autofill ──────────────────────────────────────────────────────────────

class TestAutofill:
    def test_bad_url_returns_422(self):
        u = register_and_login()
        pdf = b"%PDF-1.4 " + b"x" * 200
        resume = client.post("/api/v1/resumes/upload", headers=u["headers"],
                             files={"file": ("r.pdf", pdf, "application/pdf")}).json()
        r = client.post("/api/v1/autofill/google-form", headers=u["headers"],
                        json={"form_url": "https://example.com/not-a-form",
                              "resume_id": resume["id"]})
        assert r.status_code == 422

    def test_nonexistent_run_returns_404(self):
        u = register_and_login()
        r = client.get(f"/api/v1/autofill/{uuid.uuid4()}", headers=u["headers"])
        assert r.status_code == 404
