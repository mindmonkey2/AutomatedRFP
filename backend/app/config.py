from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_prefix="RFP_", extra="ignore")

    # The app must connect as a role that is NOT a superuser and has no BYPASSRLS,
    # otherwise Postgres row-level security is not enforced.
    database_url: str = "postgresql+psycopg://rfp:rfp@localhost:5432/rfp"
    # Optional separate (owner) connection for migrations; defaults to database_url.
    migration_database_url: str | None = None
    storage_dir: Path = BACKEND_DIR / "data" / "files"

    # Auth
    allow_signup: bool = True  # anyone can create a new organization from the sign-up page
    session_days: int = 14
    cookie_name: str = "rfp_session"
    cookie_secure: bool = False  # set true in production (HTTPS)
    cors_origins: list[str] = ["http://localhost:3000"]
    # How many reverse proxies in front of the app append the visitor's address to
    # X-Forwarded-For (e.g. 1 for nginx or Caddy -> Next.js -> API). Used only to rate-limit
    # failed logins per visitor address. 0 = no such proxy; requests arriving through the
    # bundled Next.js proxy on this machine then have no usable visitor address.
    forwarded_hops: int = 0
    # Addresses of our own frontend proxy. A request arriving from one of these stands for many
    # visitors, so it is never rate-limited as one address. Docker Compose sets this to every
    # address, because there the API port is not published and only the frontend can reach it.
    internal_proxy_cidrs: list[str] = ["127.0.0.0/8", "::1/128"]

    # Which AI runs the extraction and drafting: "claude" or "openai_compatible"
    # (local models via Ollama, vLLM, llama.cpp server, LM Studio, or any OpenAI-compatible API).
    llm_provider: str = "claude"

    # OpenAI-compatible / local model settings (used when llm_provider = "openai_compatible").
    openai_base_url: str = "http://localhost:11434/v1"  # Ollama's default
    openai_api_key: str | None = None  # not needed for local servers
    openai_model: str | None = None  # e.g. "qwen3:32b", "llama3.3:70b", "gpt-oss:20b"
    openai_timeout_s: float = 900  # local models on modest hardware can be slow
    openai_max_tokens: int = 8192
    openai_retries: int = 2  # extra attempts when the output is not valid JSON for the schema
    # "json_schema" (constrained decoding, preferred) or "json_object" / "prompt" for servers without it.
    openai_output_mode: str = "json_schema"

    # Claude settings. The key can be set in the environment or in backend/.env.
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    model: str = "claude-opus-5-5"
    effort: str = "high"
    # Server-side refusal fallback (beta). Set RFP_USE_FALLBACKS=false to disable.
    use_fallbacks: bool = True

    # Search by meaning (app/embeddings.py): "none" (keyword search only), "local" (a small model
    # in the app, CPU) or "openai_compatible" (a /v1/embeddings server such as Ollama).
    embedding_provider: str = "none"
    embedding_model: str | None = None  # local: BAAI/bge-small-en-v1.5; Ollama: e.g. nomic-embed-text
    embedding_base_url: str | None = None  # default: RFP_OPENAI_BASE_URL
    embedding_api_key: str | None = None
    embedding_cache_dir: Path | None = None  # where the local model is downloaded to
    embedding_threads: int | None = None
    vector_candidates: int = 50  # passages taken from each ranking before fusing them
    rrf_k: int = 60  # reciprocal rank fusion constant

    # Retrieval / drafting
    chunk_chars: int = 2000
    retrieve_k: int = 12
    review_threshold: float = 0.6  # answers below this confidence go to "needs_review"
    extraction_window_chars: int = 40_000
    # Background jobs (Postgres-backed queue: see app/jobs.py and app/worker.py)
    # true = the API process also runs the jobs (simplest; fine for one server). Set false and run
    # `python -m app.worker` (one or more) to process jobs in separate worker processes.
    embedded_worker: bool = True
    worker_threads: int = 4  # jobs run at once per worker process; 1-2 suits a single local GPU
    job_max_attempts: int = 3  # temporary failures (model server down, timeouts) are retried
    job_retry_base_s: float = 30  # wait before retry n: base * 4^(n-1) -> 30 s, 2 min, 8 min
    job_lease_s: float = 120  # a running job with no heartbeat for this long is taken over
    job_poll_s: float = 1.0  # idle workers check for new jobs this often

    # Limits on what one uploaded file may expand to, so a hostile file cannot exhaust the server.
    max_pdf_pages: int = 2000
    max_sheet_rows: int = 100_000  # rows across all sheets of a spreadsheet
    max_unzipped_mb: int = 300  # DOCX/XLSX are zip files; total uncompressed size


settings = Settings()
