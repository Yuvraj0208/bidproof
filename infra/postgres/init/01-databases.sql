-- Runs once on first startup with a fresh volume, as POSTGRES_USER
-- (bidproof_owner), connected to POSTGRES_DB (bidproof).

-- The application role: RLS-constrained, least privilege, NOT a table owner.
-- Table grants live in Alembic migrations. Dev password — real deployments
-- replace it.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bidproof_app') THEN
        CREATE ROLE bidproof_app LOGIN PASSWORD 'bidproof_app_dev';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE bidproof TO bidproof_app;
GRANT USAGE ON SCHEMA public TO bidproof_app;

CREATE EXTENSION IF NOT EXISTS vector;

-- Langfuse gets its own database inside the shared instance.
CREATE DATABASE langfuse;
