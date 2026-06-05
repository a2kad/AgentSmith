-- Initialize databases, roles, and extensions for AgentSmith.

CREATE ROLE agents_app LOGIN PASSWORD 'agents_app';
CREATE ROLE langfuse_app LOGIN PASSWORD 'langfuse_app';

CREATE DATABASE agents OWNER agents_app;
CREATE DATABASE langfuse OWNER langfuse_app;

\connect agents
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS architectural_decisions (
	id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	task_id TEXT NOT NULL,
	decision TEXT NOT NULL,
	rationale TEXT,
	affected_components TEXT[],
	approved_by TEXT NOT NULL,
	embedding vector(3072),
	created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS architectural_decisions_embedding_idx
	ON architectural_decisions
	USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE IF NOT EXISTS approval_requests (
	id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	thread_id TEXT NOT NULL UNIQUE,
	task_id TEXT NOT NULL,
	status TEXT DEFAULT 'pending',
	files_changed JSONB,
	security_findings JSONB,
	test_coverage FLOAT,
	tokens_used JSONB,
	thought_chain_summary TEXT,
	human_feedback TEXT,
	created_at TIMESTAMPTZ DEFAULT NOW(),
	resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS approval_requests_status_created_at_idx
	ON approval_requests (status, created_at);

CREATE TABLE IF NOT EXISTS token_usage (
	id BIGSERIAL PRIMARY KEY,
	task_id TEXT NOT NULL,
	agent_id TEXT NOT NULL,
	model TEXT NOT NULL,
	prompt_tokens INT,
	completion_tokens INT,
	cached_tokens INT,
	cost_usd NUMERIC(10,6),
	created_at TIMESTAMPTZ DEFAULT NOW()
);

\connect langfuse
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
