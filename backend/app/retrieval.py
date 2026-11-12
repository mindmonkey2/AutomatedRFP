"""Keyword retrieval over the org's passages using Postgres full-text search.

Each chunk has a generated tsvector column with a GIN index. A question becomes an OR
of its meaningful terms, ranked with ts_rank_cd. Semantic (pgvector) search can be
added next to this as a hybrid; this module is the only place that needs to change.
"""

import re
from dataclasses import dataclass

from sqlalchemy import delete, func, literal, select
from sqlalchemy.orm import Session

from .models import Chunk

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
    for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]+", question.lower()):
        w = w.strip("-")
        if len(w) >= 3 and w not in STOPWORDS and w not in terms:
            terms.append(w)
    return terms[:max_terms]


def search(session: Session, org_id: int, question: str, k: int = 12) -> list[Hit]:
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
