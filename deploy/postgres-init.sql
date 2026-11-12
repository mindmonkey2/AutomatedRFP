-- Runs once when the Postgres container is first created.
-- The app connects as "rfp", a regular (non-superuser) role, so row-level security applies.
CREATE ROLE rfp LOGIN PASSWORD 'rfp' NOSUPERUSER NOBYPASSRLS;
CREATE DATABASE rfp OWNER rfp;
CREATE DATABASE rfp_test OWNER rfp;
