"""Retrieval evaluation: does the right library passage reach the drafting model?

Loads the passages of evals/retrieval_cases.json into a temporary organization, embeds them with
the configured provider, then runs the app's real search code (app.retrieval) for every question:
keyword-only search versus hybrid (keyword + meaning). Reports recall@k (a relevant passage is in
the top k) and MRR, overall and split by whether the question reuses the passage's wording.

Usage (from backend/; needs Postgres with pgvector, like the tests):
    ../.venv/bin/python -m evals.retrieval --database-url postgresql+psycopg://rfp:rfp@localhost:5432/rfp_test
    ../.venv/bin/python -m evals.retrieval --provider openai_compatible --model nomic-embed-text   # Ollama
"""

import argparse
import json
import os
import sys
from pathlib import Path

CASES = Path(__file__).resolve().parent / "retrieval_cases.json"
KS = (1, 3, 5)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--database-url", default=os.environ.get("TEST_DATABASE_URL"))
    ap.add_argument("--provider", default="local", choices=["local", "openai_compatible"])
    ap.add_argument("--model", help="embedding model (default for local: BAAI/bge-small-en-v1.5)")
    args = ap.parse_args(argv)
    if not args.database_url:
        print("Pass --database-url (or set TEST_DATABASE_URL): a database the app's migrations have run on.",
              file=sys.stderr)
        return 2
    os.environ["RFP_DATABASE_URL"] = args.database_url
    os.environ["RFP_EMBEDDING_PROVIDER"] = args.provider
    if args.model:
        os.environ["RFP_EMBEDDING_MODEL"] = args.model

    from sqlalchemy import delete, text

    from app import embeddings, retrieval
    from app.config import settings
    from app.db import org_session
    from app.models import Chunk, Organization

    data = json.loads(CASES.read_text())
    embeddings.ensure_schema()
    embedder = embeddings.get_embedder()

    with org_session(0) as s:
        org = Organization(name="retrieval eval (temporary)")
        s.add(org)
        s.flush()
        org_id = org.id
        s.commit()
    try:
        ids: dict[int, str] = {}
        with org_session(org_id) as s:
            for p in data["passages"]:
                c = Chunk(org_id=org_id, source_type="document", source_id=0, text=p["text"], label=p["label"])
                s.add(c)
                s.flush()
                ids[c.id] = p["id"]
            s.commit()
        embeddings.embed_library(org_id, org_id)

        results = {"keyword": [], "hybrid": []}
        with org_session(org_id) as s:
            for q in data["queries"]:
                kw = retrieval.keyword_search(s, org_id, q["q"], max(KS))
                hy = retrieval.search(s, org_id, q["q"], max(KS))
                for name, hits in (("keyword", kw), ("hybrid", hy)):
                    ranked = [ids[h.chunk.id] for h in hits]
                    first = next((i for i, pid in enumerate(ranked, 1) if pid in q["relevant"]), None)
                    results[name].append({"q": q["q"], "wording": q["wording"], "rank": first})
    finally:
        with org_session(org_id) as s:
            s.execute(delete(Chunk).where(Chunk.org_id == org_id))
            s.commit()
        with org_session(0) as s:
            s.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})
            s.commit()

    def summary(rows):
        n = len(rows)
        out = {f"recall@{k}": sum(1 for r in rows if r["rank"] and r["rank"] <= k) / n for k in KS}
        out["mrr"] = sum(1 / r["rank"] for r in rows if r["rank"]) / n
        return out

    print(f"# Retrieval eval: {len(data['queries'])} questions, {len(data['passages'])} passages, "
          f"embeddings {settings.embedding_provider}:{embedder.model}\n")
    print("| Search | Questions | " + " | ".join(f"Recall@{k}" for k in KS) + " | MRR |")
    print("| --- | --- |" + " --- |" * (len(KS) + 1))
    for wording in ("all", "same", "different"):
        for name in ("keyword", "hybrid"):
            rows = [r for r in results[name] if wording == "all" or r["wording"] == wording]
            sm = summary(rows)
            print(f"| {name} ({wording} wording) | {len(rows)} | "
                  + " | ".join(f"{sm[f'recall@{k}']:.0%}" for k in KS) + f" | {sm['mrr']:.2f} |")
    print("\nMissed in the top 5 by hybrid search:")
    for r in results["hybrid"]:
        if not r["rank"] or r["rank"] > 5:
            print(f"- {r['q']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
