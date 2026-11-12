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

    # Retrieval / drafting
    chunk_chars: int = 2000
    retrieve_k: int = 12
    draft_workers: int = 4  # answers drafted in parallel; 1-2 suits a single local GPU
    review_threshold: float = 0.6  # answers below this confidence go to "needs_review"
    extraction_window_chars: int = 40_000


settings = Settings()
