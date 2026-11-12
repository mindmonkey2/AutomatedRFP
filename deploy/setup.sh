#!/bin/sh
# One-time setup for the self-hosted stack: writes .env (next to docker-compose.yml) with random
# database passwords. Never overwrites an existing .env.
set -eu
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  echo ".env already exists; leaving it unchanged."
else
  gen() { od -An -N24 -tx1 /dev/urandom | tr -d ' \n'; }
  sed -e "s/^POSTGRES_PASSWORD=__GENERATED__$/POSTGRES_PASSWORD=$(gen)/" \
      -e "s/^RFP_DB_PASSWORD=__GENERATED__$/RFP_DB_PASSWORD=$(gen)/" \
      deploy/env.example > .env
  chmod 600 .env
  echo "Wrote .env with new database passwords."
fi

cat <<'MSG'

Next:
  1. Choose the AI in .env: set ANTHROPIC_API_KEY (Claude), or the local-AI lines (Ollama).
  2. Start:   docker compose up -d --build                      (Claude)
              docker compose --profile local-ai up -d --build   (local model; first start downloads it)
  3. Open http://localhost:3000 and create your company account.

Guide: docs/self-hosting.md
MSG
