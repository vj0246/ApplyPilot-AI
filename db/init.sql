-- ApplyPilot Database Schema
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(320) UNIQUE NOT NULL,
    full_name     VARCHAR(255) NOT NULL DEFAULT '',
    password_hash VARCHAR(255),
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS profiles (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    phone            VARCHAR(50),
    location         VARCHAR(255),
    linkedin_url     VARCHAR(2048),
    github_url       VARCHAR(2048),
    portfolio_url    VARCHAR(2048),
    target_roles     TEXT[] DEFAULT '{}',
    experience_level VARCHAR(50),
    work_types       TEXT[] DEFAULT '{}',
    salary_min       INTEGER,
    salary_max       INTEGER,
    tone_preference  VARCHAR(50) DEFAULT 'professional',
    skills           TEXT[] DEFAULT '{}',
    onboarding_done  BOOLEAN DEFAULT FALSE,
    knowledge_graph  JSONB DEFAULT '{}',
    custom_instructions TEXT,
    learned_answers  JSONB DEFAULT '[]',
    sender_email     VARCHAR(320),
    smtp_host        VARCHAR(255),
    smtp_port        INTEGER,
    smtp_username    VARCHAR(320),
    smtp_password_encrypted TEXT,
    gmail_address    VARCHAR(320),
    gmail_refresh_token_encrypted TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS resumes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    filename    VARCHAR(500) NOT NULL,
    file_path   VARCHAR(1024) NOT NULL,
    file_data   BYTEA,
    file_size   INTEGER NOT NULL,
    mime_type   VARCHAR(100) NOT NULL,
    status      VARCHAR(50) DEFAULT 'processing',
    raw_text    TEXT,
    parsed_data JSONB,
    ats_score   INTEGER,
    is_primary  BOOLEAN DEFAULT TRUE,
    label       VARCHAR(255),
    error_msg   TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    source          VARCHAR(50) DEFAULT 'text',
    url             VARCHAR(2048),
    title           VARCHAR(500),
    company         VARCHAR(500),
    location        VARCHAR(500),
    work_type       VARCHAR(50),
    salary_min      INTEGER,
    salary_max      INTEGER,
    salary_currency VARCHAR(10) DEFAULT 'USD',
    description     TEXT,
    parsed_data     JSONB,
    required_skills TEXT[] DEFAULT '{}',
    keywords        TEXT[] DEFAULT '{}',
    status          VARCHAR(50) DEFAULT 'pending',
    error_msg       TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS applications (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID REFERENCES users(id) ON DELETE CASCADE,
    job_id         UUID REFERENCES jobs(id),
    resume_id      UUID REFERENCES resumes(id),
    status         VARCHAR(50) DEFAULT 'generating',
    fit_score      NUMERIC(5,2),
    fit_breakdown  JSONB,
    skill_gaps     JSONB,
    strategy       TEXT,
    cover_letter   TEXT,
    email_subject  VARCHAR(500),
    email_body     TEXT,
    resume_adapted TEXT,
    answers        JSONB,
    user_notes     TEXT,
    submitted_at   TIMESTAMPTZ,
    error_msg      TEXT,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Google Form autofill runs. Used to live as an in-memory dict in the
-- backend process — moved to a real table so a run started before a
-- backend restart (or on a different replica, if this ever scales past
-- one process) is still visible. Rows older than a day are safe to prune;
-- nothing here is meant to be permanent history.
CREATE TABLE IF NOT EXISTS autofill_runs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID REFERENCES users(id) ON DELETE CASCADE,
    job_id         UUID REFERENCES jobs(id),
    resume_id      UUID REFERENCES resumes(id),
    form_url       VARCHAR(2048) NOT NULL,
    status         VARCHAR(50) DEFAULT 'running',
    result         JSONB,
    error_msg      TEXT,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

-- The application email that goes out from the user's own address, drafted
-- separately from being sent so a person can review or edit it first, the
-- same human in the loop rule as autofill_runs above.
CREATE TABLE IF NOT EXISTS email_sends (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID REFERENCES users(id) ON DELETE CASCADE,
    job_id           UUID REFERENCES jobs(id),
    resume_id        UUID REFERENCES resumes(id),
    recipient_email  VARCHAR(320) NOT NULL,
    subject          VARCHAR(500) DEFAULT '',
    body             TEXT DEFAULT '',
    status           VARCHAR(50) DEFAULT 'draft',
    error_msg        TEXT,
    sent_at          TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resumes_user   ON resumes(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_user      ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_apps_user      ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_apps_status    ON applications(status);
CREATE INDEX IF NOT EXISTS idx_autofill_user  ON autofill_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_autofill_created ON autofill_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_email_sends_user ON email_sends(user_id);

CREATE OR REPLACE FUNCTION _updated() RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END; $$ LANGUAGE plpgsql;

DO $$ BEGIN
  CREATE TRIGGER tu  BEFORE UPDATE ON users         FOR EACH ROW EXECUTE FUNCTION _updated();
  CREATE TRIGGER tp  BEFORE UPDATE ON profiles      FOR EACH ROW EXECUTE FUNCTION _updated();
  CREATE TRIGGER tr  BEFORE UPDATE ON resumes       FOR EACH ROW EXECUTE FUNCTION _updated();
  CREATE TRIGGER tj  BEFORE UPDATE ON jobs          FOR EACH ROW EXECUTE FUNCTION _updated();
  CREATE TRIGGER ta  BEFORE UPDATE ON applications  FOR EACH ROW EXECUTE FUNCTION _updated();
  CREATE TRIGGER taf BEFORE UPDATE ON autofill_runs FOR EACH ROW EXECUTE FUNCTION _updated();
  CREATE TRIGGER tes BEFORE UPDATE ON email_sends    FOR EACH ROW EXECUTE FUNCTION _updated();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
