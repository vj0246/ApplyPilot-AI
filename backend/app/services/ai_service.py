"""
ai_service.py
--------------
Every "AI" thing in this app goes through here — parsing resumes, parsing
job posts, scoring fit, writing the cover letter/email/form answers. Runs
on Groq (llama-3.3-70b-versatile by default). If the key's missing or Groq
rate-limits us, every function falls back to plain regex so the app
doesn't just 500 on someone.

Quick map if you're tracing a request:

  upload resume -> parse_resume() -> compute_ats_score()
  add job       -> parse_job()
  hit Generate  -> analyze_fit() -> generate_cover_letter() -> generate_email() -> adapt_resume_for_job()
  form filler   -> answer_form_questions()
"""
import json
import re
import logging
from typing import Any, Dict, List, Optional

from groq import AsyncGroq
from app.core.config import settings

log = logging.getLogger(__name__)


# Appended to every system prompt that produces text a real person will read
# or that goes out under the user's name (cover letters, emails, form
# answers, the knowledge graph summary). Kept as one shared block so the
# voice stays consistent no matter which function is writing.
WRITING_STANDARDS = """
Writing standards, follow every one of these without exception:
1. Write like a real, high impact human, not like an AI and not like a template.
2. Never use an abbreviation or an acronym. Spell every word and phrase out in full. Write "for example" instead of "e.g.", "and so on" instead of "etc.", "artificial intelligence" instead of "AI", "United States" instead of "US", "application" instead of "app".
3. Never use a hyphen or a dash of any kind, anywhere, including inside compound words. If a word would normally be hyphenated, either join it into one word or rewrite the phrase with "to" or a comma instead.
4. Be concrete and specific. Every sentence should earn its place and say something a generic answer could not say.
"""


def _client() -> AsyncGroq:
    # not built at import time on purpose — if there's no key yet (normal
    # right after cloning), we want the failure to happen when someone
    # actually tries to generate something, with a message that says why
    if not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "gsk_your_key_here":
        raise ValueError(
            "GROQ_API_KEY is not set. Get a free key at https://console.groq.com "
            "and add it to your .env file."
        )
    return AsyncGroq(api_key=settings.GROQ_API_KEY)


async def _chat(prompt: str, system: str = "", temperature: float = 0.4, max_tokens: int = 2000) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = await _client().chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""
    except ValueError as e:
        log.warning(str(e))
        return ""
    except Exception as e:
        log.warning(f"Groq API error: {e}")
        return ""


async def _json_chat(prompt: str, system: str = "") -> Dict[str, Any]:
    # Groq sometimes wraps the response in ```json fences even when told
    # not to, especially on longer outputs — strip those before parsing.
    # If that still doesn't parse, grab the biggest {...} chunk and try
    # that as a last resort.
    sys = (system or "") + "\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown fences, no explanation, no extra text before or after the JSON."
    raw = (await _chat(prompt, sys, temperature=0.1)).strip()

    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        for pattern in (r"\{.*\}", r"\[.*\]"):
            m = re.search(pattern, raw, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except Exception:
                    pass
    return {}


# ── Resume parsing ───────────────────────────────────────────────────────

async def parse_resume(raw_text: str) -> Dict[str, Any]:
    system = """You are an expert resume parser with 10 years of experience in HR and recruiting.
Extract all information accurately from the resume text provided.
Return ONLY a JSON object with this exact structure:
{
  "name": "full name or empty string",
  "email": "email or empty string",
  "phone": "phone or empty string",
  "location": "city, country or empty string",
  "linkedin": "full URL or null",
  "github": "full URL or null",
  "portfolio": "full URL or null",
  "summary": "professional summary paragraph or null",
  "experience": [
    {
      "company": "company name",
      "title": "job title",
      "start": "month year or year",
      "end": "month year or Present",
      "location": "city or remote",
      "bullets": ["achievement or responsibility"]
    }
  ],
  "education": [
    {
      "school": "institution name",
      "degree": "degree type",
      "field": "field of study",
      "year": "graduation year",
      "gpa": "GPA or null"
    }
  ],
  "skills": ["skill1", "skill2"],
  "programming_languages": ["Python", "JavaScript"],
  "certifications": ["certification name"],
  "projects": [
    {
      "name": "project name",
      "description": "what it does",
      "tech": ["technologies used"],
      "url": "URL or null"
    }
  ],
  "awards": ["award or achievement"]
}"""

    result = await _json_chat(f"Parse this resume:\n\n{raw_text[:6000]}", system)
    return result if result else _fallback_parse_resume(raw_text)


def _fallback_parse_resume(text: str) -> Dict[str, Any]:
    result = {
        "name": "", "email": "", "phone": "", "location": "",
        "linkedin": None, "github": None, "portfolio": None,
        "summary": None, "experience": [], "education": [],
        "skills": [], "programming_languages": [], "certifications": [],
        "projects": [], "awards": []
    }

    m = re.search(r"[\w._%+-]+@[\w.-]+\.\w{2,}", text)
    if m:
        result["email"] = m.group()

    m = re.search(r"(\+?\d{1,3}[\s.-]?)?(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})", text)
    if m:
        result["phone"] = m.group()

    m = re.search(r"linkedin\.com/in/([\w-]+)", text, re.I)
    if m:
        result["linkedin"] = f"https://linkedin.com/in/{m.group(1)}"
    m = re.search(r"github\.com/([\w-]+)", text, re.I)
    if m:
        result["github"] = f"https://github.com/{m.group(1)}"

    TECH = [
        "Python", "JavaScript", "TypeScript", "React", "Vue", "Angular",
        "Node.js", "Express", "FastAPI", "Django", "Flask", "Spring",
        "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
        "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Terraform",
        "Git", "Linux", "REST", "GraphQL", "gRPC", "Kafka",
        "TensorFlow", "PyTorch", "scikit-learn", "Pandas", "NumPy",
        "Java", "C++", "C#", "Go", "Rust", "Swift", "Kotlin", "Ruby",
        "HTML", "CSS", "Sass", "Tailwind", "Next.js", "Nuxt",
        "CI/CD", "GitHub Actions", "Jenkins", "Ansible",
    ]
    result["skills"] = [k for k in TECH if re.search(r"\b" + re.escape(k) + r"\b", text, re.I)]
    result["programming_languages"] = [
        s for s in result["skills"]
        if s in {"Python","JavaScript","TypeScript","Java","C++","C#","Go","Rust","Ruby","Swift","Kotlin","PHP","Scala"}
    ]

    # first non-blank, non-email line under 60 chars — works more often
    # than you'd expect since names usually sit alone at the top
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:5]:
        if "@" not in line and len(line) < 60 and not re.match(r"^\d", line):
            result["name"] = line
            break

    return result


async def compute_ats_score(parsed: Dict[str, Any]) -> int:
    # no AI call here — this is just "are the standard fields present",
    # weights below are eyeballed against a few real resumes, not an
    # official ATS spec
    score = 0
    if parsed.get("email"):            score += 10
    if parsed.get("phone"):            score += 5
    if parsed.get("linkedin"):         score += 5
    if parsed.get("summary"):          score += 10
    score += min(25, len(parsed.get("experience", [])) * 8)
    if parsed.get("education"):        score += 10
    score += min(15, len(parsed.get("skills", [])) * 1)
    if parsed.get("projects"):         score += 5
    if parsed.get("certifications"):   score += 5
    if parsed.get("programming_languages"): score += 5
    if parsed.get("github"):           score += 5
    return min(100, score)


# ── Job parsing ──────────────────────────────────────────────────────────

async def parse_job(description: str, url: str = "") -> Dict[str, Any]:
    system = """You are a senior recruiting professional who analyses job postings.
Extract all key information. Return ONLY this JSON structure:
{
  "title": "exact job title",
  "company": "company name",
  "location": "city, country or Remote",
  "work_type": "remote|hybrid|onsite",
  "salary_min": null,
  "salary_max": null,
  "salary_currency": "USD",
  "required_skills": ["must-have skill"],
  "nice_to_have": ["preferred skill"],
  "experience_years": null,
  "education_required": "Bachelor's / Master's / etc or null",
  "responsibilities": ["key responsibility"],
  "benefits": ["benefit"],
  "keywords": ["important keyword for ATS"],
  "culture": ["culture signal"],
  "apply_email": null
}"""

    result = await _json_chat(
        f"URL: {url}\n\nJob Description:\n{description[:5000]}",
        system,
    )
    return result if result else _fallback_parse_job(description)


def _fallback_parse_job(text: str) -> Dict[str, Any]:
    work_type = "onsite"
    if re.search(r"\bremote\b", text, re.I):
        work_type = "remote"
    elif re.search(r"\bhybrid\b", text, re.I):
        work_type = "hybrid"

    sm = re.search(r"\$(\d{2,3})[kK]?\s*[-–—]\s*\$?(\d{2,3})[kK]?", text)
    s_min = s_max = None
    if sm:
        lo, hi = int(sm.group(1)), int(sm.group(2))
        s_min = lo * 1000 if lo < 500 else lo
        s_max = hi * 1000 if hi < 500 else hi

    TECH = ["Python","JavaScript","TypeScript","React","Node.js","SQL","AWS","Docker","Kubernetes","Git"]
    skills = [k for k in TECH if re.search(r"\b" + re.escape(k) + r"\b", text, re.I)]

    return {
        "title": "", "company": "", "location": "", "work_type": work_type,
        "salary_min": s_min, "salary_max": s_max, "salary_currency": "USD",
        "required_skills": skills, "nice_to_have": [],
        "experience_years": None, "education_required": None,
        "responsibilities": [], "benefits": [], "keywords": skills,
        "culture": [], "apply_email": None,
    }


# ── Fit analysis ─────────────────────────────────────────────────────────
# Pure Python on purpose, no AI call — set intersection on skills, weighted
# 0-100. Faster and more consistent than asking the model to "score" it,
# and the cover letter prompt below depends on this number staying stable.

async def analyze_fit(
    resume_parsed: Dict,
    job_parsed: Dict,
    profile: Optional[Dict] = None,
) -> Dict[str, Any]:
    user_skills = set(
        s.lower() for s in (
            (resume_parsed.get("skills") or []) +
            (resume_parsed.get("programming_languages") or []) +
            ((profile or {}).get("skills") or [])
        )
    )

    required = set(s.lower() for s in (job_parsed.get("required_skills") or []))
    nice     = set(s.lower() for s in (job_parsed.get("nice_to_have") or []))

    matched  = user_skills & required
    missing  = required - user_skills
    bonus    = user_skills & nice

    skills_score = (len(matched) / max(len(required), 1)) * 100 if required else 70.0
    exp_needed   = job_parsed.get("experience_years") or 0
    user_exp     = len(resume_parsed.get("experience") or [])
    exp_score    = min(100.0, (user_exp / max(exp_needed / 2, 1)) * 100) if exp_needed else 75.0
    overall      = round(skills_score * 0.55 + exp_score * 0.45, 1)

    gaps = [{"skill": s, "type": "required"} for s in list(missing)[:6]]
    gaps += [{"skill": s, "type": "nice_to_have"} for s in list(nice - user_skills)[:3]]

    return {
        "overall": overall,
        "skills_match": round(skills_score, 1),
        "experience_match": round(exp_score, 1),
        "matched_skills": sorted(matched),
        "missing_required": sorted(missing),
        "bonus_skills": sorted(bonus),
        "gaps": gaps,
    }


# ── Cover letter ─────────────────────────────────────────────────────────
# The banned-phrases list exists because early drafts of this prompt kept
# producing the exact "I am excited to apply and believe my skills make me
# a great fit" letter everyone's sick of reading.

async def generate_cover_letter(
    resume_parsed: Dict,
    job_parsed: Dict,
    fit: Dict,
    tone: str = "professional",
    extra_context: str = "",
) -> str:
    name        = resume_parsed.get("name", "")
    exp         = resume_parsed.get("experience", [])
    current     = f"{exp[0].get('title', '')} at {exp[0].get('company', '')}" if exp else ""
    top_bullet  = exp[0].get("bullets", [""])[0] if exp else ""
    matched     = ", ".join(list(fit.get("matched_skills", []))[:5])
    skills_raw  = ", ".join((resume_parsed.get("skills") or [])[:8])
    job_title   = job_parsed.get("title", "the role")
    company     = job_parsed.get("company", "the company")
    culture     = ", ".join((job_parsed.get("culture") or [])[:3])
    fit_pct     = fit.get("overall", 75)

    system = f"""You are an expert career coach who writes cover letters that actually get interviews.
Your letters sound like a real, thoughtful person wrote them — not an AI, not a template.

Writing rules (follow strictly):
1. Open with a strong, specific hook — reference something real about {company} or the role
2. Never use these phrases: "I am excited to apply", "I am writing to express my interest", "I would be a great fit", "passion for", "hard worker", "team player", "leverage my skills"
3. Use the candidate's real achievements with numbers where available
4. Show you understand what {company} actually does and values
5. Three paragraphs max — each one punchy and purposeful
6. End with a confident, specific call to action
7. Total length: 180–240 words
8. Tone: {tone}
9. Sound human — vary sentence length, include one specific detail that shows you did your homework
{WRITING_STANDARDS}
Return ONLY the letter body. No subject line, no "Dear Hiring Manager" header, no sign-off."""

    prompt = f"""Write a cover letter for this candidate:

Name: {name}
Current / Recent role: {current}
Top achievement: {top_bullet}
Skills they have that match the job: {matched}
Full skill set: {skills_raw}
Fit score: {fit_pct:.0f}/100

Target role: {job_title} at {company}
Company culture signals: {culture}
Extra context from applicant: {extra_context}"""

    # temperature 0.7 on purpose — this is the one spot we want real
    # variation between runs, it's what makes the Regenerate button
    # on the review page actually useful
    result = await _chat(prompt, system, temperature=0.7, max_tokens=600)
    return result.strip() if result else _fallback_cover_letter(name, job_parsed, fit)


def _fallback_cover_letter(name: str, job: Dict, fit: Dict) -> str:
    t = job.get("title", "this role")
    c = job.get("company", "your company")
    sk = ", ".join(list(fit.get("matched_skills", []))[:3]) or "strong technical foundations"
    return (
        f"The {t} role at {c} stands out to me because it aligns precisely "
        f"with the work I've been building toward.\n\n"
        f"With hands on experience in {sk}, I've built a track record of delivering "
        f"meaningful results in fast moving environments. I combine technical depth "
        f"with the communication skills to turn complex work into clear outcomes.\n\n"
        f"I'd welcome the chance to talk through what you're building and how I can "
        f"contribute from day one.\n\nBest,\n{name}"
    )


# ── Application email ────────────────────────────────────────────────────

async def generate_email(
    name: str,
    job_parsed: Dict,
    fit: Dict,
    extra_context: str = "",
    knowledge_graph: Optional[Dict] = None,
) -> Dict[str, str]:
    job_title    = job_parsed.get("title", "the role")
    company      = job_parsed.get("company", "the company")
    matched      = ", ".join(list(fit.get("matched_skills", []))[:6])
    top_skill    = list(fit.get("matched_skills", []))[:1]
    top_skill_str = top_skill[0] if top_skill else "relevant experience"
    responsibilities = ", ".join((job_parsed.get("responsibilities") or [])[:5])
    required_skills  = ", ".join((job_parsed.get("required_skills") or [])[:8])
    culture      = ", ".join((job_parsed.get("culture") or [])[:3])
    fit_pct      = fit.get("overall", 75)
    graph_context = _knowledge_graph_context(knowledge_graph)

    system = f"""You are a senior professional job email writer with deep experience getting candidates
interviews at competitive companies. Every email you write is read closely against the exact job
description it responds to, so it must be tightly and visibly aligned with what that role actually
asks for, not a generic application anyone could send.

Non negotiable rules:
1. Read the required skills and responsibilities given below and mirror the two or three that matter
   most, using the candidate's real matched skills and fit, never a skill they do not have
2. Subject line format: "Application for [Role Title], [Full Name]"
3. Body: 3 to 4 sentences only, no filler, every sentence must connect a real fact about the
   candidate to something specific this job actually asks for
4. Do not say "I hope this email finds you well" or any other empty opener
5. Sound like a real, thoughtful, confident professional wrote this personally for this one role,
   never like a template that got the company name swapped in
6. End with a clear, specific next step
{WRITING_STANDARDS}
Return JSON: {{"subject": "...", "body": "..."}}"""

    prompt = f"""Write an application email about this exact job description, sent on the candidate's
behalf to a recipient at the company.

Candidate: {name}
Role: {job_title} at {company}
Fit score against this job description: {fit_pct:.0f} out of 100
Candidate's matched skills for this job description: {matched or top_skill_str}
This job description's required skills: {required_skills}
This job description's key responsibilities: {responsibilities}
This company's culture signals: {culture}
{graph_context}
Extra context from the candidate: {extra_context}"""

    result = await _json_chat(prompt, system)
    if result and result.get("subject"):
        return result

    return {
        "subject": f"Application for {job_title}, {name}",
        "body": (
            f"Hi,\n\n"
            f"I'm writing to apply for the {job_title} position at {company}. "
            f"My background in {top_skill_str} is a direct match for what you've described. "
            f"I've applied this in production settings with measurable results.\n\n"
            f"I've attached my resume and cover letter. "
            f"I'd be glad to jump on a quick call to discuss.\n\n"
            f"Best,\n{name}"
        )
    }


# ── Knowledge graph ──────────────────────────────────────────────────────
# Built once from a short personality and background interview (see
# app/routers/profile.py for the question set), then read back into every
# form answer and email so the AI is grounded in who the candidate actually
# is, not just what a resume happens to list. Stored as one structured JSON
# object on the profile rather than a real graph database — for the depth
# this app needs, a flat set of labeled facts is enough, and it stays a
# single readable object instead of a node and edge store to maintain.

async def build_knowledge_graph(qa_pairs: List[Dict[str, str]]) -> Dict[str, Any]:
    system = f"""You are building a structured knowledge graph of a person from their own answers to
personality and background questions. Read every answer carefully and extract what is really
there, do not invent anything that was not said or clearly implied.

Return ONLY this JSON structure:
{{
  "identity": "one sentence describing who this person is professionally",
  "values": ["a value that clearly matters to them"],
  "strengths": ["a genuine strength, backed by something they said"],
  "motivations": ["what actually drives them, in their own framing"],
  "work_style": ["how they operate day to day"],
  "achievements": [{{"title": "short label", "summary": "what happened and why it mattered"}}],
  "goals": ["a stated or clearly implied goal"],
  "communication_style": "a short description of how they naturally express themselves"
}}
{WRITING_STANDARDS}"""

    qa_formatted = "\n\n".join(f"Question: {p.get('question','')}\nAnswer: {p.get('answer','')}" for p in qa_pairs)
    result = await _json_chat(f"Build the knowledge graph from these answers:\n\n{qa_formatted}", system)
    return result if result else {
        "identity": "", "values": [], "strengths": [], "motivations": [],
        "work_style": [], "achievements": [], "goals": [], "communication_style": "",
    }


def merge_knowledge_graph(old: Optional[Dict], new: Dict) -> Dict:
    # Answering the questionnaire again should grow someone's memory, not
    # wipe it. List fields union and dedupe case insensitively, achievements
    # dedupe by title, and the two single sentence fields only get replaced
    # when the new answer actually said something.
    old = old or {}

    def _merge_list(key: str) -> List[str]:
        seen: Dict[str, str] = {}
        for value in (old.get(key) or []) + (new.get(key) or []):
            if value and value.strip():
                seen[value.strip().lower()] = value.strip()
        return list(seen.values())

    merged_achievements: Dict[str, Dict[str, str]] = {}
    for a in (old.get("achievements") or []) + (new.get("achievements") or []):
        title = (a.get("title") or "").strip()
        if title:
            merged_achievements[title.lower()] = a

    return {
        "identity": new.get("identity") or old.get("identity") or "",
        "values": _merge_list("values"),
        "strengths": _merge_list("strengths"),
        "motivations": _merge_list("motivations"),
        "work_style": _merge_list("work_style"),
        "achievements": list(merged_achievements.values()),
        "goals": _merge_list("goals"),
        "communication_style": new.get("communication_style") or old.get("communication_style") or "",
    }


def _knowledge_graph_context(knowledge_graph: Optional[Dict]) -> str:
    if not knowledge_graph:
        return ""
    g = knowledge_graph
    lines = []
    if g.get("identity"):
        lines.append(f"Who they are: {g['identity']}")
    if g.get("values"):
        lines.append(f"What they value: {', '.join(g['values'][:5])}")
    if g.get("strengths"):
        lines.append(f"Genuine strengths: {', '.join(g['strengths'][:5])}")
    if g.get("motivations"):
        lines.append(f"What drives them: {', '.join(g['motivations'][:3])}")
    if g.get("work_style"):
        lines.append(f"How they work: {', '.join(g['work_style'][:3])}")
    if g.get("achievements"):
        top = g["achievements"][:2]
        lines.append("Personal stories: " + "; ".join(f"{a.get('title','')}, {a.get('summary','')}" for a in top))
    if g.get("goals"):
        lines.append(f"What they are working toward: {', '.join(g['goals'][:3])}")
    if g.get("communication_style"):
        lines.append(f"How they naturally speak: {g['communication_style']}")
    return "Knowledge graph of the candidate as a person, drawn from their own words:\n" + "\n".join(lines) if lines else ""


# ── Form question answers ────────────────────────────────────────────────
# Same function the Google Form and Microsoft Form autofill engines call —
# one prompt to maintain instead of two near-identical ones.

async def answer_form_questions(
    questions: List[str],
    resume_parsed: Dict,
    job_parsed: Optional[Dict],
    extra_context: str = "",
    knowledge_graph: Optional[Dict] = None,
) -> List[Dict[str, str]]:
    name     = resume_parsed.get("name", "the applicant")
    exp      = resume_parsed.get("experience", [])
    recent   = f"{exp[0].get('title','')} at {exp[0].get('company','')}" if exp else "recent role"
    bullets  = "; ".join((exp[0].get("bullets") or [])[:3]) if exp else ""
    skills   = ", ".join((resume_parsed.get("skills") or [])[:10])
    jt       = (job_parsed or {}).get("title", "this role")
    company  = (job_parsed or {}).get("company", "this company")
    culture  = ", ".join(((job_parsed or {}).get("culture") or [])[:3])
    graph_context = _knowledge_graph_context(knowledge_graph)

    system = f"""You are helping {name} fill in a job application for {jt} at {company}, section by
section, question by question. You are reading the whole form the way a thoughtful human
assistant would, not answering each question in isolation.
Write answers that sound like a real, thoughtful human wrote them, not AI generated.

Grounding facts about {name}:
- Recent role: {recent}
- Key achievements: {bullets}
- Technical skills: {skills}
- Extra context: {extra_context}
{graph_context}

Rules for every answer:
1. Be specific, use real facts from the candidate's background above
2. Keep answers concise: 2 to 4 sentences for short questions, 4 to 6 for long ones
3. Never use: "I am passionate about", "synergy", "leverage", "hard working", "team player"
4. Sound genuine, confident, and direct
5. If a question asks about salary, give a reasonable range based on industry norms
6. For "Why this company?", reference something specific about {company} (culture: {culture})
{WRITING_STANDARDS}
Return a JSON array, one object per question:
[{{"question": "...", "answer": "..."}}]"""

    qs_formatted = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
    result = await _json_chat(
        f"Answer these application questions:\n\n{qs_formatted}",
        system,
    )

    if isinstance(result, list) and result:
        return result

    answers = []
    for q in questions:
        answers.append({
            "question": q,
            "answer": f"Based on my experience as {recent} with skills in {skills.split(',')[0].strip()}, I would bring a focused and results-oriented approach to this."
        })
    return answers


# ── Resume adaptation ────────────────────────────────────────────────────
# The trickiest prompt here — if this ever "helpfully" adds a skill the
# candidate doesn't have to hit a JD keyword, that's a resume that lies.
# Rules below are blunt and repeated on purpose. Tested by feeding it a
# resume missing an obvious keyword to confirm it reframes existing
# bullets instead of inventing the missing skill.

async def adapt_resume_for_job(
    raw_text: str,
    job_parsed: Dict,
    fit: Dict,
) -> str:
    keywords = ", ".join((job_parsed.get("required_skills") or [])[:10])
    missing  = ", ".join(list(fit.get("missing_required") or [])[:5])

    system = f"""You are an expert resume writer and ATS optimization specialist.

CRITICAL RULES, never break these:
1. NEVER invent skills, tools, or experience the candidate has not mentioned
2. NEVER change job titles, company names, dates, or GPAs
3. ONLY reframe existing bullets to naturally incorporate relevant keywords
4. Improve weak action verbs (use: Built, Delivered, Reduced, Grew, Shipped, Automated, Led, Designed)
5. Add metrics where implied but not explicit (for instance, "improved performance" becomes "improved performance by about 30 percent"), mark estimated figures with the word about
6. Keep the same overall structure and length
{WRITING_STANDARDS}
Return only the improved resume text."""

    prompt = f"""Optimize this resume for the target job.

Target job keywords to incorporate naturally: {keywords}
Skills gap to address where honest: {missing}

Resume:
{raw_text[:3000]}"""

    # lower temperature than the cover letter — rewriting facts about
    # someone's career should be boring and consistent, not "creative"
    result = await _chat(prompt, system, temperature=0.3, max_tokens=1500)
    return result.strip() if result else raw_text
