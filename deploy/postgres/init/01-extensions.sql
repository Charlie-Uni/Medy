-- Runs once when the PostgreSQL volume is first created (docker-entrypoint-initdb.d).
-- Only the vector extension is enabled here; roles, RLS and schema come from migrations (M1).
CREATE EXTENSION IF NOT EXISTS vector;
