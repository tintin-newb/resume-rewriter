-- db/schema.sql

-- Enable UUID extension if needed in future
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main table tracking each resume rewrite run
CREATE TABLE IF NOT EXISTS job_applications (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(128) NOT NULL,
    company VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL,
    job_url TEXT,
    job_description TEXT NOT NULL,
    match_tier VARCHAR(64),
    status VARCHAR(64) DEFAULT 'PROCESSING',
    rewritten_resume_path TEXT,
    referral_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_company_job UNIQUE (company, job_id)
);

-- Indexes for quick lookups during CLI idempotency checks
CREATE INDEX IF NOT EXISTS idx_job_lookup 
ON job_applications (LOWER(company), LOWER(job_id));

CREATE INDEX IF NOT EXISTS idx_job_url 
ON job_applications (job_url);