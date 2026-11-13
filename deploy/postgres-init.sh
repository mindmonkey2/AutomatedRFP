#!/bin/sh
# Runs once, when the Postgres volume is first created (docker-entrypoint-initdb.d).
# The app connects as "rfp", a regular role (not a superuser, no BYPASSRLS), so Postgres
# row-level security keeps each company's data separate. Its password comes from .env.
set -eu
psql -v ON_ERROR_STOP=1 -v pw="$RFP_DB_PASSWORD" --username "$POSTGRES_USER" --dbname postgres <<'SQL'
CREATE ROLE rfp LOGIN PASSWORD :'pw' NOSUPERUSER NOBYPASSRLS;
CREATE DATABASE rfp OWNER rfp;
SQL
# Search by meaning uses pgvector; only a superuser can install it (the image includes it).
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname rfp -c "CREATE EXTENSION IF NOT EXISTS vector;"
