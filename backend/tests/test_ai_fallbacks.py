"""
Tests for the regex-based fallback logic in ai_service.py — the code
path that runs when Groq is unavailable or GROQ_API_KEY isn't set.

These need no database and no network call, which is exactly the point:
the fallback exists so the app degrades gracefully instead of failing
outright, and that fallback logic deserves to be tested without needing
the thing it's a fallback FOR.

Run: pytest tests/test_ai_fallbacks.py -v
"""
import pytest
from app.services.ai_service import (
    _fallback_parse_resume,
    _fallback_parse_job,
    _fallback_cover_letter,
    analyze_fit,
    compute_ats_score,
)


SAMPLE_RESUME = """
Alex Rivera
alex@example.com | (415) 555-0120 | San Francisco, CA
github.com/alexrivera | linkedin.com/in/alexrivera

Summary
Full-stack engineer with 4 years building scalable APIs and React apps.

Experience
Senior Software Engineer — DataFlow Inc (2022–Present)
- Built real-time data pipeline processing 5M events/day
- Reduced API latency by 35% through caching redesign

Skills: Python, FastAPI, React, TypeScript, PostgreSQL, Redis, Docker, AWS
"""

SAMPLE_JOB = """
Senior Backend Engineer at TechCorp
Location: Remote
We're hiring a backend engineer to work on our Python/PostgreSQL stack.
Salary: $150k - $200k
Requirements: Python, PostgreSQL, Docker, Redis, AWS
"""


class TestFallbackResumeParsing:
    def test_extracts_email(self):
        result = _fallback_parse_resume(SAMPLE_RESUME)
        assert result["email"] == "alex@example.com"

    def test_extracts_phone(self):
        result = _fallback_parse_resume(SAMPLE_RESUME)
        assert "415" in result["phone"]

    def test_extracts_linkedin_with_https_prefix(self):
        result = _fallback_parse_resume(SAMPLE_RESUME)
        assert result["linkedin"] == "https://linkedin.com/in/alexrivera"

    def test_extracts_github_with_https_prefix(self):
        result = _fallback_parse_resume(SAMPLE_RESUME)
        assert result["github"] == "https://github.com/alexrivera"

    def test_extracts_known_tech_skills(self):
        result = _fallback_parse_resume(SAMPLE_RESUME)
        assert "Python" in result["skills"]
        assert "React" in result["skills"]
        assert "PostgreSQL" in result["skills"]

    def test_does_not_invent_skills_not_in_text(self):
        result = _fallback_parse_resume(SAMPLE_RESUME)
        assert "Kubernetes" not in result["skills"]
        assert "Rust" not in result["skills"]

    def test_programming_languages_is_subset_of_skills(self):
        result = _fallback_parse_resume(SAMPLE_RESUME)
        assert set(result["programming_languages"]).issubset(set(result["skills"]))

    def test_extracts_name_from_first_line(self):
        result = _fallback_parse_resume(SAMPLE_RESUME)
        assert result["name"] == "Alex Rivera"

    def test_empty_text_does_not_crash(self):
        result = _fallback_parse_resume("")
        assert result["email"] == ""
        assert result["skills"] == []


class TestFallbackJobParsing:
    def test_detects_remote_work_type(self):
        result = _fallback_parse_job(SAMPLE_JOB)
        assert result["work_type"] == "remote"

    def test_detects_hybrid_work_type(self):
        result = _fallback_parse_job("This is a hybrid role in Austin.")
        assert result["work_type"] == "hybrid"

    def test_defaults_to_onsite_when_unspecified(self):
        result = _fallback_parse_job("Come work at our office in Austin.")
        assert result["work_type"] == "onsite"

    def test_extracts_salary_range(self):
        result = _fallback_parse_job(SAMPLE_JOB)
        assert result["salary_min"] == 150000
        assert result["salary_max"] == 200000

    def test_extracts_required_skills(self):
        result = _fallback_parse_job(SAMPLE_JOB)
        assert "Python" in result["required_skills"]
        assert "Docker" in result["required_skills"]

    def test_no_salary_mentioned_returns_none(self):
        result = _fallback_parse_job("We are hiring a great engineer.")
        assert result["salary_min"] is None
        assert result["salary_max"] is None


class TestFitAnalysis:
    """analyze_fit() is pure Python, no AI call at all — always testable."""

    @pytest.mark.asyncio
    async def test_perfect_skill_match_scores_high(self):
        resume = {"skills": ["Python", "Docker", "AWS"], "experience": [{}, {}]}
        job = {"required_skills": ["Python", "Docker", "AWS"], "experience_years": 2}
        fit = await analyze_fit(resume, job)
        assert fit["skills_match"] == 100.0
        assert fit["overall"] > 80

    @pytest.mark.asyncio
    async def test_no_skill_overlap_scores_low(self):
        resume = {"skills": ["Java", "Spring"], "experience": []}
        job = {"required_skills": ["Python", "Django"], "experience_years": 3}
        fit = await analyze_fit(resume, job)
        assert fit["skills_match"] == 0.0

    @pytest.mark.asyncio
    async def test_missing_required_lists_the_gap(self):
        resume = {"skills": ["Python"], "experience": []}
        job = {"required_skills": ["Python", "Kubernetes"], "experience_years": 0}
        fit = await analyze_fit(resume, job)
        assert "kubernetes" in fit["missing_required"]
        assert "python" in fit["matched_skills"]

    @pytest.mark.asyncio
    async def test_job_with_no_required_skills_does_not_divide_by_zero(self):
        resume = {"skills": ["Python"], "experience": []}
        job = {"required_skills": [], "experience_years": 0}
        fit = await analyze_fit(resume, job)
        assert fit["skills_match"] == 70.0  # neutral default, see analyze_fit()

    @pytest.mark.asyncio
    async def test_profile_skills_count_toward_match(self):
        # skills can come from the resume OR the user's profile —
        # confirms both sources are actually combined, not just resume
        resume = {"skills": [], "experience": []}
        profile = {"skills": ["Python"]}
        job = {"required_skills": ["Python"], "experience_years": 0}
        fit = await analyze_fit(resume, job, profile)
        assert fit["skills_match"] == 100.0


class TestATSScore:
    @pytest.mark.asyncio
    async def test_full_profile_scores_high(self):
        parsed = {
            "email": "a@b.com", "phone": "555-1234", "linkedin": "https://...",
            "summary": "A summary", "experience": [{}, {}, {}],
            "education": [{}], "skills": ["a", "b", "c"], "projects": [{}],
            "certifications": ["x"], "programming_languages": ["Python"],
            "github": "https://...",
        }
        score = await compute_ats_score(parsed)
        assert score >= 80

    @pytest.mark.asyncio
    async def test_empty_profile_scores_zero(self):
        score = await compute_ats_score({})
        assert score == 0

    @pytest.mark.asyncio
    async def test_score_never_exceeds_100(self):
        # pile on way more than the weights could naturally produce,
        # confirms the min(100, ...) cap actually holds
        parsed = {
            "email": "a@b.com", "phone": "1", "linkedin": "1", "summary": "1",
            "experience": [{}] * 20, "education": [{}], "skills": ["x"] * 50,
            "projects": [{}], "certifications": ["x"],
            "programming_languages": ["x"], "github": "1",
        }
        score = await compute_ats_score(parsed)
        assert score == 100


class TestCoverLetterFallback:
    def test_includes_candidate_name(self):
        letter = _fallback_cover_letter("Jordan Lee", {"title": "Engineer", "company": "Acme"}, {})
        assert "Jordan Lee" in letter

    def test_includes_company_and_role(self):
        letter = _fallback_cover_letter("Jordan", {"title": "Backend Engineer", "company": "Acme"}, {})
        assert "Backend Engineer" in letter
        assert "Acme" in letter

    def test_never_uses_banned_opening_phrase(self):
        # the whole point of the banned-phrases rule in the real AI prompt —
        # confirm the fallback template doesn't violate its own rule either
        letter = _fallback_cover_letter("Jordan", {"title": "Engineer", "company": "Acme"}, {})
        assert "i am excited to apply" not in letter.lower()
        assert "i am writing to express my interest" not in letter.lower()
