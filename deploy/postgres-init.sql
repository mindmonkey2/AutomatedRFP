-- Runs once when the Postgres container is first created.
-- The app connects as "rfp", a regular (non-superuser) role, so row-level security applies.
CREATE ROLE rfp LOGIN PASSWORD 'rfp' NOSUPERUSER NOBYPASSRLS;
CREATE DATABASE rfp OWNER rfp;
CREATE DATABASE rfp_test OWNER rfp;

-- Search by meaning (optional) uses the pgvector extension, which only a superuser can install.
-- Needs a Postgres with pgvector available (e.g. the pgvector/pgvector images); skipped otherwise.
SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') AS has_vector \gset
\if :has_vector
\c rfp
CREATE EXTENSION IF NOT EXISTS vector;
\c rfp_test
CREATE EXTENSION IF NOT EXISTS vector;
\endif
