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

    # Claude settings. The key can be set in the environment or in backend/.env.
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    model: str = "claude-opus-5-5"
    effort: str = "high"
    # Server-side refusal fallback (beta). Set RFP_USE_FALLBACKS=false to disable.
    use_fallbacks: bool = True

    # Retrieval / drafting
    chunk_chars: int = 2000
    retrieve_k: int = 12
    review_threshold: float = 0.6  # answers below this confidence go to "needs_review"
    extraction_window_chars: int = 40_000


settings = Settings()
