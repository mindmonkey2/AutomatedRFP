"""Load evaluation cases: a page-tagged solicitation plus a hand-labelled answer key."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.llm import REQUIREMENT_KINDS

CASES_DIR = Path(__file__).resolve().parent / "cases"
# Text rebuilt locally by `python -m evals.fetch` for cases not redistributed in the repo.
FETCHED_NAME = "document.fetched.txt"


@dataclass
class GoldRequirement:
    id: str
    kind: str
    page: int | None
    mandatory: bool
    needs_response: bool
    quote: str


@dataclass
class Trap:
    page: int | None
    quote: str
    why: str


@dataclass
class Case:
    id: str
    title: str
    source: str  # "synthetic" or "real"
    status: str  # "reviewed" or "draft" (drafts are skipped unless asked for)
    document: str
    requirements: list[GoldRequirement]
    traps: list[Trap] = field(default_factory=list)
    source_url: str | None = None
    labelled_by: str | None = None
    local_only: bool = False  # text is fetched from the source, not stored in the repo


def normalize(text: str) -> str:
    return " ".join(text.split())


def load_case(folder: Path) -> Case | None:
    """Load a case; returns None for a fetch-only case whose text has not been fetched yet."""
    gold = json.loads((folder / "gold.json").read_text())
    local_only = "fetch" in gold
    doc_path = folder / (FETCHED_NAME if local_only else "document.txt")
    if not doc_path.exists():
        return None
    doc = doc_path.read_text()
    return Case(local_only=local_only,
        id=gold["id"], title=gold["title"], source=gold.get("source", "real"),
        status=gold.get("status", "draft"), document=doc, source_url=gold.get("source_url"),
        labelled_by=gold.get("labelled_by"),
        requirements=[GoldRequirement(**r) for r in gold["requirements"]],
        traps=[Trap(**t) for t in gold.get("traps", [])],
    )


def load_cases(ids: list[str] | None = None, include_drafts: bool = False) -> list[Case]:
    cases = [c for d in sorted(CASES_DIR.iterdir()) if (d / "gold.json").exists() and (c := load_case(d))]
    if ids:
        cases = [c for c in cases if c.id in ids]
    if not include_drafts:
        cases = [c for c in cases if c.status == "reviewed"]
    return cases


def validate(case: Case) -> list[str]:
    """Problems with an answer key. An empty list means the case is usable."""
    problems = []
    doc = normalize(case.document)
    ids = [r.id for r in case.requirements]
    if len(ids) != len(set(ids)):
        problems.append("duplicate requirement ids")
    pages = {int(p) for p in re.findall(r"\[Page (\d+)\]", case.document)}
    for r in case.requirements:
        if r.kind not in REQUIREMENT_KINDS:
            problems.append(f"{r.id}: unknown kind {r.kind!r}")
        if normalize(r.quote) not in doc:
            problems.append(f"{r.id}: quote not found in document: {r.quote[:60]!r}")
        if pages and r.page is not None and r.page not in pages:
            problems.append(f"{r.id}: page {r.page} does not exist")
    for t in case.traps:
        if normalize(t.quote) not in doc:
            problems.append(f"trap quote not found in document: {t.quote[:60]!r}")
    return problems


def unfetched_case_ids() -> list[str]:
    """Fetch-only cases whose source text is not on this machine yet."""
    return [d.name for d in sorted(CASES_DIR.iterdir())
            if (d / "gold.json").exists() and "fetch" in json.loads((d / "gold.json").read_text())
            and not (d / FETCHED_NAME).exists()]
