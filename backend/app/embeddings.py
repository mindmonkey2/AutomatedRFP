"""Embeddings for search by meaning, stored in Postgres with pgvector.

Keyword search (retrieval.py) misses passages that say the same thing in other words: a question
about "pupils" and a past proposal about "students", "annual revenue" and "turnover". Each library
passage also gets an embedding vector; a search runs both and fuses the rankings.

Providers (RFP_EMBEDDING_PROVIDER):
- "none" (default): keyword search only.
- "local": a small model running in the app itself on the CPU (fastembed / ONNX). The model
  (BAAI/bge-small-en-v1.5 by default, ~70 MB) is downloaded once, then nothing leaves the server.
- "openai_compatible": any /v1/embeddings endpoint, e.g. Ollama with nomic-embed-text or bge-m3.

Vectors live in chunk_embeddings, one row per (passage, model), so switching models re-embeds in
the background without losing the old vectors until the new ones exist. The table is outside the
SQLAlchemy models because the vector type needs the pgvector extension, which only a database
superuser can install; without it the app keeps working on keyword search.
"""

import logging
import threading
from typing import Protocol

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from .config import settings
from .llm import LLMError

log = logging.getLogger(__name__)

TABLE = "chunk_embeddings"
ORG_SETTING = "NULLIF(current_setting('app.org_id', true), '')::integer"

DEFAULT_LOCAL_MODEL = "BAAI/bge-small-en-v1.5"

_SCHEMA = [
    f"""CREATE TABLE IF NOT EXISTS {TABLE} (
        chunk_id integer NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
        org_id integer NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        model varchar(200) NOT NULL,
        dim integer NOT NULL,
        embedding vector NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (chunk_id, model)
    )""",
    f"CREATE INDEX IF NOT EXISTS ix_{TABLE}_org_model ON {TABLE} (org_id, model)",
    f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY",
    f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY",
]
_POLICY = (f"CREATE POLICY tenant_isolation ON {TABLE} "
           f"USING (org_id = {ORG_SETTING}) WITH CHECK (org_id = {ORG_SETTING})")


class EmbeddingsUnavailable(RuntimeError):
    pass


# ---------------------------------------------------------------- schema


def vector_extension_installed(conn: Connection) -> bool:
    return bool(conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).first())


def table_exists(conn: Connection) -> bool:
    return bool(conn.execute(text("SELECT to_regclass(:t)"), {"t": TABLE}).scalar())


def create_schema(conn: Connection) -> bool:
    """Create the embeddings table (idempotent). Returns False if pgvector is not installed."""
    if not vector_extension_installed(conn):
        return False
    for stmt in _SCHEMA:
        conn.execute(text(stmt))
    if not conn.execute(text("SELECT 1 FROM pg_policies WHERE tablename = :t AND policyname = 'tenant_isolation'"),
                        {"t": TABLE}).first():
        conn.execute(text(_POLICY))
    return True


INSTALL_HINT = ("Search by meaning needs the pgvector extension. As a database superuser run: "
                "CREATE EXTENSION vector;  (Docker Compose: docker compose exec postgres psql -U postgres -d rfp "
                "-c 'CREATE EXTENSION vector')")


def ensure_schema() -> None:
    """At startup when embeddings are enabled: create the table if pgvector is there, else explain."""
    from .db import engine

    with engine.begin() as conn:
        if table_exists(conn):
            return
        if not create_schema(conn):
            raise EmbeddingsUnavailable(INSTALL_HINT)


def ensure_index(s: Session, dim: int) -> None:
    """HNSW index for one vector size. Vectors of different models have different sizes, so the
    column is untyped and each size gets an expression index (the pgvector-recommended pattern)."""
    dim = int(dim)
    s.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{TABLE}_hnsw_{dim} ON {TABLE} "
                   f"USING hnsw ((embedding::vector({dim})) vector_cosine_ops) WHERE dim = {dim}"))


# ---------------------------------------------------------------- providers


class Embedder(Protocol):
    model: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class LocalEmbedder:
    """A small ONNX model in-process (no GPU needed)."""

    def __init__(self, model: str | None = None):
        try:
            from fastembed import TextEmbedding
        except ImportError as e:
            raise EmbeddingsUnavailable(
                "RFP_EMBEDDING_PROVIDER=local needs fastembed: pip install -r requirements-embeddings.txt") from e
        self.model = model or DEFAULT_LOCAL_MODEL
        cache = str(settings.embedding_cache_dir) if settings.embedding_cache_dir else None
        self._m = TextEmbedding(model_name=self.model, cache_dir=cache, threads=settings.embedding_threads)
        self._lock = threading.Lock()  # one ONNX session; keep calls from worker threads orderly

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            return [v.tolist() for v in self._m.passage_embed(texts, batch_size=32)]

    def embed_query(self, text_: str) -> list[float]:
        with self._lock:
            return next(iter(self._m.query_embed(text_))).tolist()


class OpenAICompatibleEmbedder:
    """POST /v1/embeddings (Ollama, vLLM, LM Studio, llama.cpp server, hosted APIs)."""

    def __init__(self, model: str | None = None, client: httpx.Client | None = None):
        if not (model or settings.embedding_model):
            raise EmbeddingsUnavailable("Set RFP_EMBEDDING_MODEL (e.g. nomic-embed-text) for openai_compatible embeddings.")
        self.model = model or settings.embedding_model
        base = (settings.embedding_base_url or settings.openai_base_url).rstrip("/")
        key = settings.embedding_api_key or settings.openai_api_key
        self.client = client or httpx.Client(base_url=base, timeout=120,
                                             headers={"Authorization": f"Bearer {key}"} if key else {})

    def _embed(self, texts: list[str]) -> list[list[float]]:
        try:
            r = self.client.post("/embeddings", json={"model": self.model, "input": texts})
        except httpx.HTTPError as e:
            raise LLMError(f"Could not reach the embeddings server: {e}", retryable=True) from e
        if r.status_code >= 400:
            temporary = r.status_code in (408, 429) or r.status_code >= 500
            raise LLMError(f"Embeddings server error {r.status_code}: {r.text[:300]}", retryable=temporary)
        data = sorted(r.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 64):
            out += self._embed(texts[i : i + 64])
        return out

    def embed_query(self, text_: str) -> list[float]:
        return self._embed([text_])[0]


_embedder: Embedder | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> Embedder | None:
    """The configured embedder, or None for keyword-only search."""
    global _embedder
    provider = settings.embedding_provider.lower()
    if provider == "none":
        return None
    with _embedder_lock:
        if _embedder is None:
            if provider == "local":
                _embedder = LocalEmbedder(settings.embedding_model)
            elif provider == "openai_compatible":
                _embedder = OpenAICompatibleEmbedder()
            else:
                raise ValueError(f"Unknown RFP_EMBEDDING_PROVIDER {provider!r}: use none, local or openai_compatible")
        return _embedder


def set_embedder(e: Embedder | None) -> None:
    """Used by tests to install a fake."""
    global _embedder
    _embedder = e


def vector_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"


# ---------------------------------------------------------------- background job


EMBED_BATCH = 64


def embed_library(org_id: int, _target_id: int, job=None) -> None:
    """Job: embed every passage of the organization that has no vector for the current model.
    Re-queries after each batch, so passages added while it runs are picked up too."""
    from . import db

    embedder = get_embedder()
    if embedder is None:
        return
    with db.org_session(org_id) as s:
        if not table_exists(s.connection()):
            raise EmbeddingsUnavailable(INSTALL_HINT)
        while True:
            rows = s.execute(text(f"""
                SELECT c.id, c.label, c.heading, c.text FROM chunks c
                LEFT JOIN {TABLE} e ON e.chunk_id = c.id AND e.model = :model
                WHERE c.org_id = :org AND e.chunk_id IS NULL
                ORDER BY c.id LIMIT :n"""), {"model": embedder.model, "org": org_id, "n": EMBED_BATCH}).all()
            if not rows:
                break
            vectors = embedder.embed_documents([passage_text(r.label, r.heading, r.text) for r in rows])
            dim = len(vectors[0])
            ensure_index(s, dim)
            for r, v in zip(rows, vectors, strict=True):
                s.execute(text(f"""
                    INSERT INTO {TABLE} (chunk_id, org_id, model, dim, embedding)
                    VALUES (:c, :org, :model, :dim, CAST(:v AS vector))
                    ON CONFLICT (chunk_id, model) DO NOTHING"""),
                    {"c": r.id, "org": org_id, "model": embedder.model, "dim": dim, "v": vector_literal(v)})
            s.commit()  # progress is kept even if a later batch fails
            log.info("embedded %d passage(s) for org %s with %s", len(rows), org_id, embedder.model)


def passage_text(label: str | None, heading: str | None, body: str) -> str:
    """What gets embedded: the source name and section help (e.g. "Project record: Oak Hill")."""
    return "\n".join(x for x in (label, heading, body) if x)


def enqueue_embedding(s: Session, org_id: int) -> None:
    """Called wherever passages are added; one queued job per organization covers them all."""
    if settings.embedding_provider.lower() != "none":
        from . import jobs

        jobs.enqueue(s, org_id, "embed_library", org_id)
