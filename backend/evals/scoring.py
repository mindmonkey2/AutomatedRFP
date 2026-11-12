"""Match extracted requirements to the answer key and compute metrics.

Matching: a gold requirement counts as found when one extracted requirement covers at
least MATCH_THRESHOLD of the gold quote's content words (looking at the extracted
requirement's verbatim quote and its restated text together). Matching is one-to-one,
best pairs first, so one extracted item that lumps several obligations together only
gets credit for one of them. That is deliberate: a merged requirement hides the others
from the compliance checklist.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field

from app.llm import ExtractedRequirement

from .dataset import Case

MATCH_THRESHOLD = 0.6
TRAP_THRESHOLD = 0.6

_STOP = set("""the and for with that this from are was were will shall must may any all each its their
their your our been has have had not but per into than such upon within which who whom""".split())


def content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())
    return {w for w in words if (len(w) > 2 or w.isdigit()) and w not in _STOP}


def coverage(target: str, extracted: ExtractedRequirement) -> float:
    t = content_words(target)
    if not t:
        return 0.0
    e = content_words(extracted.source_quote) | content_words(extracted.text)
    return len(t & e) / len(t)


@dataclass
class CaseResult:
    case_id: str
    title: str
    gold_total: int
    extracted_total: int
    matched: list[tuple[str, int, float]] = field(default_factory=list)  # (gold id, extracted index, score)
    missed: list[str] = field(default_factory=list)  # gold ids
    unmatched_extracted: list[int] = field(default_factory=list)
    trap_hits: list[str] = field(default_factory=list)  # trap quotes extracted as requirements
    kind_correct: int = 0
    page_correct: int = 0
    page_checked: int = 0
    mandatory_total: int = 0
    mandatory_found: int = 0
    by_kind: dict[str, list[int]] = field(default_factory=dict)  # kind -> [found, total]
    error: str | None = None

    @property
    def recall(self) -> float:
        return len(self.matched) / self.gold_total if self.gold_total else 0.0


def score_case(case: Case, extracted: list[ExtractedRequirement]) -> CaseResult:
    res = CaseResult(case.id, case.title, len(case.requirements), len(extracted))
    pairs = []
    for gi, g in enumerate(case.requirements):
        for ei, e in enumerate(extracted):
            s = coverage(g.quote, e)
            if s >= MATCH_THRESHOLD:
                pairs.append((s, gi, ei))
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
    used_g, used_e = set(), set()
    for s, gi, ei in pairs:
        if gi in used_g or ei in used_e:
            continue
        used_g.add(gi)
        used_e.add(ei)
        res.matched.append((case.requirements[gi].id, ei, round(s, 3)))

    by_kind: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    matched_by_gold = {gid: ei for gid, ei, _ in res.matched}
    for g in case.requirements:
        by_kind[g.kind][1] += 1
        res.mandatory_total += g.mandatory
        ei = matched_by_gold.get(g.id)
        if ei is None:
            res.missed.append(g.id)
            continue
        e = extracted[ei]
        by_kind[g.kind][0] += 1
        res.mandatory_found += g.mandatory
        res.kind_correct += e.kind == g.kind
        if g.page is not None:
            res.page_checked += 1
            res.page_correct += e.page == g.page
    res.by_kind = dict(by_kind)

    res.unmatched_extracted = [i for i in range(len(extracted)) if i not in used_e]
    for i in res.unmatched_extracted:
        for t in case.traps:
            if coverage(t.quote, extracted[i]) >= TRAP_THRESHOLD:
                res.trap_hits.append(t.quote)
                break
    return res


def summarize(results: list[CaseResult], traps_total: int) -> dict:
    ok = [r for r in results if r.error is None]
    gold = sum(r.gold_total for r in ok)
    found = sum(len(r.matched) for r in ok)
    matched = found or 1
    by_kind: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in ok:
        for k, (f, t) in r.by_kind.items():
            by_kind[k][0] += f
            by_kind[k][1] += t
    return {
        "cases": len(results),
        "cases_failed": len(results) - len(ok),
        "gold_requirements": gold,
        "found": found,
        "recall": round(found / gold, 4) if gold else 0.0,
        "mandatory_recall": round(
            sum(r.mandatory_found for r in ok) / max(sum(r.mandatory_total for r in ok), 1), 4
        ),
        "kind_accuracy": round(sum(r.kind_correct for r in ok) / matched, 4),
        "page_accuracy": round(sum(r.page_correct for r in ok) / max(sum(r.page_checked for r in ok), 1), 4),
        "extracted": sum(r.extracted_total for r in ok),
        "unmatched_extracted": sum(len(r.unmatched_extracted) for r in ok),
        "trap_hits": sum(len(r.trap_hits) for r in ok),
        "traps_total": traps_total,
        "recall_by_kind": {k: {"found": f, "total": t, "recall": round(f / t, 4)} for k, (f, t) in sorted(by_kind.items())},
    }
