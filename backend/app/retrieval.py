"""Retrieval over the org's passages: keyword search, plus search by meaning when enabled.

Keyword: each chunk has a generated tsvector column with a GIN index; a question becomes an OR
of its meaningful terms, ranked with ts_rank_cd.

Meaning (RFP_EMBEDDING_PROVIDER, see embeddings.py): the question's embedding is compared with
the passages' embeddings (cosine distance, HNSW index). The two rankings are fused with
reciprocal rank fusion: each passage scores sum(1 / (k + rank)) over the lists it appears in, so a
passage both searches agree on comes first, and one found by only one search still gets in. If
embeddings are off or fail, search is keyword-only, as before.
"""

import logging


from dataclasses import dataclass

from sqlalchemy import delete, func, literal, select, text
from sqlalchemy.orm import Session

from . import embeddings
from .config import settings
from .models import Chunk

log = logging.getLogger(__name__)
from .parsing import words

STOPWORDS = set(
    """a an and are as at be been by can could do does for from has have how if in into is it its
    may must of on or our shall should such than that the their them then there these they this
    to under upon was we were what when where which while who will with within would you your
    any all each other provide describe include including please submit proposer offeror bidder
    contractor vendor respondent""".split()
)


@dataclass
class Hit:
    chunk: Chunk
    score: float  # higher is better


def add_chunk(session: Session, chunk: Chunk) -> Chunk:
    session.add(chunk)
    session.flush()
    return chunk


def remove_source(session: Session, org_id: int, source_type: str, source_id: int) -> None:
    session.execute(
        delete(Chunk).where(
            Chunk.org_id == org_id, Chunk.source_type == source_type, Chunk.source_id == source_id
        )
    )


def query_terms(question: str, max_terms: int = 24) -> list[str]:
    terms: list[str] = []
    for w in words(question):  # any script: Hindi, Tamil, accented Latin...
        if len(w) >= 3 and w not in STOPWORDS and w not in terms:
            terms.append(w)
    return terms[:max_terms]


def keyword_search(session: Session, org_id: int, question: str, k: int = 12) -> list[Hit]:
    terms = query_terms(question)
    if not terms:
        return []
    # OR of per-term queries; plainto_tsquery handles stemming, hyphens and escaping.
    tsq = None
    for t in terms:
        q = func.plainto_tsquery("english", literal(t))
        tsq = q if tsq is None else tsq.op("||")(q)
    rank = func.ts_rank_cd(Chunk.tsv, tsq).label("rank")
    rows = session.execute(
        select(Chunk, rank)
        .where(Chunk.org_id == org_id, Chunk.tsv.op("@@")(tsq))
        .order_by(rank.desc(), Chunk.id)
        .limit(k)
    ).all()
    return [Hit(c, float(r)) for c, r in rows]


def vector_search(session: Session, org_id: int, question: str, k: int = 12) -> list[Hit]:
    """Passages closest in meaning to the question (empty if embeddings are off or unavailable)."""
    embedder = embeddings.get_embedder()
    if embedder is None:
        return []
    qv = embedder.embed_query(question)
    dim = len(qv)
    # Filtering by organization and model after an approximate index scan could return too few
    # rows; iterative scans keep reading the index until k rows pass the filter (pgvector 0.8+).
    session.execute(text("SET LOCAL hnsw.iterative_scan = 'relaxed_order'"))
    rows = session.execute(text(f"""
        SELECT chunk_id, embedding::vector({dim}) <=> CAST(:q AS vector({dim})) AS distance
        FROM {embeddings.TABLE}
        WHERE org_id = :org AND model = :model AND dim = {dim}
        ORDER BY embedding::vector({dim}) <=> CAST(:q AS vector({dim}))
        LIMIT :k"""), {"q": embeddings.vector_literal(qv), "org": org_id, "model": embedder.model, "k": k}).all()
    chunks = {c.id: c for c in session.scalars(select(Chunk).where(Chunk.id.in_([r.chunk_id for r in rows])))}
    return [Hit(chunks[r.chunk_id], 1 - float(r.distance)) for r in rows if r.chunk_id in chunks]


def fuse(rankings: list[list[Hit]], k: int, rrf_k: int | None = None) -> list[Hit]:
    """Reciprocal rank fusion of several rankings into one (score = sum of 1/(rrf_k + rank))."""
    rrf_k = settings.rrf_k if rrf_k is None else rrf_k
    scores: dict[int, float] = {}
    chunks: dict[int, Chunk] = {}
    for ranking in rankings:
        for rank, h in enumerate(ranking, start=1):
            scores[h.chunk.id] = scores.get(h.chunk.id, 0.0) + 1 / (rrf_k + rank)
            chunks[h.chunk.id] = h.chunk
    best = sorted(scores, key=lambda cid: (-scores[cid], cid))[:k]
    return [Hit(chunks[cid], round(scores[cid], 6)) for cid in best]


def search(session: Session, org_id: int, question: str, k: int = 12) -> list[Hit]:
    """Hybrid search when embeddings are enabled, keyword search otherwise."""
    if settings.embedding_provider.lower() == "none":
        return keyword_search(session, org_id, question, k)
    n = max(k, settings.vector_candidates)
    keyword = keyword_search(session, org_id, question, n)
    try:
        with session.begin_nested():  # a failed vector query must not spoil the caller's transaction
            semantic = vector_search(session, org_id, question, n)
    except Exception as e:  # noqa: BLE001 - embeddings server down, extension missing...: degrade
        log.warning("search by meaning unavailable, using keyword search only: %s", e)
        semantic = []
    if not semantic:
        return keyword[:k]
    return fuse([keyword, semantic], k)
