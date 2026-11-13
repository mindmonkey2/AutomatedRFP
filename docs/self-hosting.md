# Self-hosting RFP Engine

Run the whole app on your own server with Docker Compose. Your documents and data stay in your
own database. With the `local-ai` option, the AI runs on your hardware too, and nothing leaves
the machine.

## What runs

| Service | What it does | Reachable from outside? |
| --- | --- | --- |
| `frontend` | The web app (Next.js). Forwards API calls to `api` | Yes: port 3000 (this machine only by default) |
| `api` | The FastAPI backend | No |
| `worker` | Background jobs: reading documents, extracting requirements, drafting answers | No |
| `postgres` | Database, with row-level security between companies | No |
| `migrate` | Applies database migrations on every start, then exits | No |
| `caddy` (profile `https`) | HTTPS for your domain, certificate obtained and renewed automatically | Yes: ports 80 and 443 |
| `ollama` (profile `local-ai`) | A model server for running the AI on this machine | No |

Uploaded files are kept in the `files` volume and the database in `pgdata`. Back up both.

## Install

Needs Docker with the Compose plugin (or Podman with a compose provider) and about 2 GB of disk
space for the images. A local AI model needs much more; see below.

```bash
git clone https://github.com/mindmonkey2/AutomatedRFP.git
cd AutomatedRFP
./deploy/setup.sh                 # writes .env with random database passwords
```

Then choose the AI in `.env`:

**Claude:** set `ANTHROPIC_API_KEY`, then:

```bash
docker compose up -d --build
```

**A model on this machine (Ollama):** uncomment the local-AI lines in `.env` and choose a model
(`RFP_OPENAI_MODEL=qwen3:32b`, for example), then:

```bash
docker compose --profile local-ai up -d --build
# with an NVIDIA GPU (needs the NVIDIA Container Toolkit):
docker compose -f docker-compose.yml -f deploy/compose.gpu.yaml --profile local-ai up -d --build
```

The first start downloads the model, which can take a while (`docker compose logs -f ollama-pull`).
Rough sizing: a 30B-class model needs a GPU with 24 GB or more, or about 32 GB of RAM to run
slowly on a CPU. Check your choice with the evaluation harness before relying on it (see the
README's "AI providers" section). To use a model server you already run elsewhere, set
`RFP_OPENAI_BASE_URL` to it instead of using the profile.

Open http://localhost:3000 and create your company account. Then set `RFP_ALLOW_SIGNUP=false`
in `.env` and run `docker compose up -d`, so new people can join only by invite.

## Search by meaning

By default the stack also searches the library by meaning, not only by keyword, so a question
worded differently from your past proposals still finds them. It uses a small model that runs on the
CPU inside the app. The model is downloaded once (about 65 MB) into the `files` volume, and nothing
is sent anywhere after that. Alternatives in `.env`:

- `RFP_EMBEDDING_PROVIDER=openai_compatible` and `RFP_EMBEDDING_MODEL=nomic-embed-text` to use Ollama
  (`docker compose exec ollama ollama pull nomic-embed-text`), or any other embeddings server via
  `RFP_EMBEDDING_BASE_URL`.
- `RFP_EMBEDDING_PROVIDER=none` for keyword search only.

Changing the model re-embeds the library in the background. Search keeps working meanwhile.

**Upgrading from a version before search by meaning:** the database image is now
`pgvector/pgvector:pg18` (the same Postgres 18, plus the extension). Existing databases need the
extension enabled once:

```bash
docker compose up -d --build
docker compose exec postgres psql -U postgres -d rfp -c 'CREATE EXTENSION IF NOT EXISTS vector'
docker compose restart api worker   # they create the search table at startup
```

Until then the app logs this instruction and uses keyword search.

## Serve it on your domain with HTTPS

1. Point your domain's DNS (an A/AAAA record) at the server, and open ports 80 and 443.
2. In `.env`, set:
   ```
   SITE_ADDRESS=rfp.example.com
   PUBLIC_URL=https://rfp.example.com
   COOKIE_SECURE=true
   FRONTEND_HTTPS=true
   FORWARDED_HOPS=1
   ```
3. Start with the profile: `docker compose --profile https up -d --build`

`PUBLIC_URL` must match the address in the browser exactly: the API refuses changes coming from
any other origin. `FORWARDED_HOPS=1` lets the login limiter see each visitor's address through
Caddy. Without it, failed logins are limited per account only.

## Day-to-day

| Task | Command |
| --- | --- |
| See what is running | `docker compose ps` |
| Follow the logs | `docker compose logs -f api worker` |
| Upgrade | `git pull && docker compose up -d --build` (migrations run automatically) |
| More throughput | `WORKER_THREADS=8` in `.env`, or `docker compose up -d --scale worker=3` |
| Back up the database | `docker compose exec postgres pg_dump -U postgres rfp > rfp-$(date +%F).sql` |
| Back up uploaded files | `docker run --rm -v rfp-engine_files:/data -v "$PWD":/backup alpine tar czf /backup/files-$(date +%F).tgz -C /data .` |
| Stop | `docker compose down` (data is kept; `down -v` deletes it) |

Jobs are durable. Stopping or upgrading the worker mid-job loses nothing: running jobs get
2 minutes to finish, and anything cut off is picked up again after the restart.

## Security notes

- Only the frontend (or Caddy) publishes a port. The API, database and model server are reachable
  only inside the compose network.
- `.env` holds the database passwords. `setup.sh` creates it readable by you only, and git ignores it.
- The app connects to Postgres as `rfp`, a regular role, so row-level security separates companies.
  The `postgres` superuser is used only to create that role on first start.
- With the default Claude provider, document text is sent to Anthropic's API to process your bids.
  With `local-ai`, it never leaves the server.
