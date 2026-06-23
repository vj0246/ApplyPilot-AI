"""Seed demo data. Run: docker compose exec backend python seed.py"""
import asyncio
from app.core.database import AsyncSessionLocal
from app.core.auth import hash_password
from app.models import Application, Job, Profile, Resume, User
from sqlalchemy import select


async def seed():
    async with AsyncSessionLocal() as db:
        # Check if already seeded
        ex = await db.execute(select(User).where(User.email == "demo@applypilot.dev"))
        if ex.scalar_one_or_none():
            print("✅ Already seeded — skipping")
            return

        # Demo user
        user = User(
            email="demo@applypilot.dev",
            full_name="Alex Rivera",
            password_hash=hash_password("Demo1234!"),
        )
        db.add(user)
        await db.flush()

        db.add(Profile(
            user_id=user.id,
            location="San Francisco, CA",
            linkedin_url="https://linkedin.com/in/alexrivera",
            github_url="https://github.com/alexrivera",
            target_roles=["Software Engineer", "Backend Engineer"],
            experience_level="mid",
            work_types=["remote", "hybrid"],
            salary_min=120000,
            salary_max=180000,
            tone_preference="professional",
            skills=["Python", "React", "PostgreSQL", "Docker", "FastAPI", "TypeScript"],
            onboarding_done=True,
        ))

        resume = Resume(
            user_id=user.id,
            filename="alex_rivera_resume.pdf",
            file_path="/app/uploads/demo/resume.pdf",
            file_size=48200,
            mime_type="application/pdf",
            status="ready",
            label="Main Resume",
            is_primary=True,
            ats_score=84,
            raw_text="Alex Rivera\nalex@example.com | (415) 555-0120 | San Francisco, CA\ngithub.com/alexrivera | linkedin.com/in/alexrivera\n\nSummary\nFull-stack engineer with 4 years building scalable APIs and React applications.\n\nExperience\nSenior Software Engineer — DataFlow Inc (2022–Present)\n• Built real-time data pipeline processing 5M events/day using Python and Kafka\n• Reduced API latency by 35% through caching strategy redesign\n• Led migration to microservices, cutting deployment time by 60%\n\nSoftware Engineer — WebAgency (2020–2022)\n• Developed 15+ REST APIs serving 200k monthly users\n• Built React dashboard reducing support tickets by 40%\n\nSkills: Python, FastAPI, React, TypeScript, PostgreSQL, Redis, Docker, AWS, Git",
            parsed_data={
                "name": "Alex Rivera",
                "email": "alex@example.com",
                "phone": "(415) 555-0120",
                "location": "San Francisco, CA",
                "linkedin": "https://linkedin.com/in/alexrivera",
                "github": "https://github.com/alexrivera",
                "summary": "Full-stack engineer with 4 years building scalable APIs and React applications.",
                "experience": [
                    {
                        "company": "DataFlow Inc",
                        "title": "Senior Software Engineer",
                        "start": "2022",
                        "end": "Present",
                        "bullets": [
                            "Built real-time data pipeline processing 5M events/day",
                            "Reduced API latency by 35% through caching redesign",
                            "Led microservices migration, cutting deploy time by 60%"
                        ]
                    },
                    {
                        "company": "WebAgency",
                        "title": "Software Engineer",
                        "start": "2020",
                        "end": "2022",
                        "bullets": [
                            "Developed 15+ REST APIs for 200k monthly users",
                            "Built React dashboard reducing support tickets by 40%"
                        ]
                    }
                ],
                "education": [{"school": "UC Berkeley", "degree": "B.S.", "field": "Computer Science", "year": "2020"}],
                "skills": ["Python", "FastAPI", "React", "TypeScript", "PostgreSQL", "Redis", "Docker", "AWS", "Git"],
                "programming_languages": ["Python", "TypeScript", "JavaScript"],
            }
        )
        db.add(resume)

        # Demo job
        job = Job(
            user_id=user.id,
            source="url",
            url="https://jobs.lever.co/example/swe-backend",
            title="Senior Backend Engineer",
            company="TechCorp",
            location="Remote",
            work_type="remote",
            salary_min=150000,
            salary_max=200000,
            status="ready",
            required_skills=["Python", "PostgreSQL", "Docker", "Redis", "AWS"],
            keywords=["microservices", "API design", "distributed systems"],
            parsed_data={
                "title": "Senior Backend Engineer",
                "company": "TechCorp",
                "location": "Remote",
                "work_type": "remote",
                "salary_min": 150000,
                "salary_max": 200000,
                "required_skills": ["Python", "PostgreSQL", "Docker", "Redis", "AWS"],
                "nice_to_have": ["Kubernetes", "gRPC"],
                "culture": ["fast-paced", "ownership", "remote-first"],
            }
        )
        db.add(job)
        await db.flush()

        # Demo application
        app = Application(
            user_id=user.id,
            job_id=job.id,
            resume_id=resume.id,
            status="ready",
            fit_score=87.5,
            fit_breakdown={
                "overall": 87.5, "skills_match": 90.0, "experience_match": 85.0,
                "matched_skills": ["Python", "PostgreSQL", "Docker", "Redis", "AWS"],
                "missing_required": [],
            },
            skill_gaps=[{"skill": "Kubernetes", "type": "nice_to_have"}],
            strategy="Strong match at 87.5/100. Lead with the data pipeline and latency optimization work — exactly what TechCorp values.",
            cover_letter="TechCorp's approach to distributed systems engineering is something I've been following closely — it lines up directly with what I've been building at DataFlow.\n\nOver the past two years I've shipped a real-time pipeline handling 5M events per day, redesigned our caching layer to cut API latency by 35%, and led a microservices migration that reduced deployment time by 60%. Each of these challenges pushed me to think carefully about system design, reliability, and developer experience — the same tensions your team deals with at scale.\n\nI'd welcome the chance to talk through what you're building and how I can contribute from the start.\n\nBest,\nAlex Rivera",
            email_subject="Application: Senior Backend Engineer — Alex Rivera",
            email_body="Hi,\n\nI'm applying for the Senior Backend Engineer role at TechCorp. My background building high-throughput data systems at DataFlow Inc aligns directly with what you're looking for — I've reduced latency by 35% and shipped pipelines processing 5M events/day.\n\nResume attached. Happy to connect this week.\n\nBest,\nAlex Rivera",
        )
        db.add(app)
        await db.commit()

    print("✅ Demo data seeded!")
    print("   Email:    demo@applypilot.dev")
    print("   Password: Demo1234!")


if __name__ == "__main__":
    asyncio.run(seed())
