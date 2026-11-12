"""Requirement-extraction evaluation.

Runs the app's real extraction pipeline (app.pipeline.extract_from_text) on every
reviewed case and scores it against the hand-labelled answer key.

Usage (from backend/):
    ../.venv/bin/python -m evals.extraction                       # Claude, settings from .env
    ../.venv/bin/python -m evals.extraction --model claude-sonnet-5-5 --effort medium
    ../.venv/bin/python -m evals.extraction --runner keyword      # no-AI baseline, free
    ../.venv/bin/python -m evals.extraction --min-recall 0.95     # exit 1 below the bar (CI gate)
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.llm import ExtractedRequirement
from app.parsing import obligation_sentences

from .dataset import Case, load_cases, validate
from .scoring import CaseResult, score_case, summarize

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# USD per million tokens, used only to estimate the cost of a run.
PRICES = {
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_read": 0.20},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_read": 0.10},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_read": 0.01},
}
CACHE_WRITE_MULTIPLIER = 1.25  # 5-minute cache writes


def keyword_runner(case: Case) -> list[ExtractedRequirement]:
    """Baseline with no AI: every sentence containing an obligation word is a requirement."""
    return [
        ExtractedRequirement(text=s, kind="submission", section=None, page=p, source_quote=s,
                             mandatory=True, needs_response=False, page_limit=None)
        for p, s in obligation_sentences(case.document)
    ]


def make_claude_runner():
    from app.llm import ClaudeLLM
    from app.pipeline import extract_from_text

    llm = ClaudeLLM()

    def run(case: Case) -> list[ExtractedRequirement]:
        return extract_from_text(case.document, llm)[1]

    return run, llm


def estimate_cost(model: str, usage: dict) -> float | None:
    p = PRICES.get(model)
    if not p:
        return None
    return round((
        usage["input_tokens"] * p["input"]
        + usage["cache_creation_input_tokens"] * p["input"] * CACHE_WRITE_MULTIPLIER
        + usage["cache_read_input_tokens"] * p["cache_read"]
        + usage["output_tokens"] * p["output"]
    ) / 1_000_000, 4)


def run_case(case: Case, runner) -> tuple[CaseResult, list[ExtractedRequirement], float]:
    start = time.monotonic()
    try:
        extracted = runner(case)
    except Exception as e:  # noqa: BLE001 - one failing case must not stop the run
        res = CaseResult(case.id, case.title, len(case.requirements), 0, error=str(e)[:500])
        return res, [], time.monotonic() - start
    return score_case(case, extracted), extracted, time.monotonic() - start


def to_markdown(report: dict) -> str:
    s, m = report["summary"], report["meta"]
    lines = [
        f"# Requirement extraction eval: {m['runner']}" + (f" ({m['model']}, effort {m['effort']})" if m["runner"] == "claude" else ""),
        "",
        f"Run {m['started_at']} · {s['cases']} cases · {s['gold_requirements']} labelled requirements"
        + (f" · {m['seconds']:.0f}s" if m.get("seconds") else "")
        + (f" · est. ${m['cost_usd']:.2f}" if m.get("cost_usd") is not None else ""),
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| **Recall** (requirements found) | **{s['recall']:.1%}** ({s['found']}/{s['gold_requirements']}) |",
        f"| Mandatory recall | {s['mandatory_recall']:.1%} |",
        f"| Kind accuracy (of found) | {s['kind_accuracy']:.1%} |",
        f"| Page accuracy (of found) | {s['page_accuracy']:.1%} |",
        f"| Traps extracted (owner obligations taken as bidder requirements) | {s['trap_hits']} of {s['traps_total']} |",
        f"| Extracted items not in the answer key | {s['unmatched_extracted']} of {s['extracted']} |",
        "",
        "## Recall by requirement kind",
        "",
        "| Kind | Found | Recall |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {k} | {v['found']}/{v['total']} | {v['recall']:.0%} |" for k, v in s["recall_by_kind"].items()]
    lines += ["", "## By case", "", "| Case | Recall | Mandatory | Extracted | Traps hit |", "| --- | --- | --- | --- | --- |"]
    for c in report["cases"]:
        if c["error"]:
            lines.append(f"| {c['id']} | error: {c['error'][:80]} | | | |")
        else:
            lines.append(f"| {c['id']} | {c['recall']:.0%} ({c['found']}/{c['gold']}) | "
                         f"{c['mandatory_found']}/{c['mandatory_total']} | {c['extracted']} | {len(c['trap_hits'])} |")
    lines += ["", "## Missed requirements", ""]
    any_missed = False
    for c in report["cases"]:
        for g in c["missed"]:
            any_missed = True
            lines.append(f"- `{c['id']}` {g['id']} ({g['kind']}{', mandatory' if g['mandatory'] else ''}): \"{g['quote']}\"")
    if not any_missed:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runner", choices=["claude", "keyword"], default="claude")
    ap.add_argument("--model", help="Claude model (default: RFP_MODEL setting)")
    ap.add_argument("--effort", help="low|medium|high|xhigh|max (default: RFP_EFFORT setting)")
    ap.add_argument("--cases", help="comma-separated case ids (default: all reviewed cases)")
    ap.add_argument("--include-drafts", action="store_true", help="also run cases whose answer key is not reviewed")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", type=Path, default=RESULTS_DIR)
    ap.add_argument("--min-recall", type=float, help="exit with status 1 if recall is below this")
    args = ap.parse_args(argv)

    cases = load_cases(args.cases.split(",") if args.cases else None, args.include_drafts)
    if not cases:
        print("No cases to run.", file=sys.stderr)
        return 2
    for c in cases:
        if problems := validate(c):
            print(f"Answer key problems in {c.id}:\n  " + "\n  ".join(problems), file=sys.stderr)
            return 2

    llm = None
    if args.runner == "claude":
        if args.model:
            settings.model = args.model
        if args.effort:
            settings.effort = args.effort
        runner, llm = make_claude_runner()
    else:
        runner = keyword_runner

    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        outcomes = list(pool.map(lambda c: run_case(c, runner), cases))
    seconds = time.monotonic() - t0

    results = [o[0] for o in outcomes]
    summary = summarize(results, sum(len(c.traps) for c in cases))
    meta = {"runner": args.runner, "started_at": started.strftime("%Y-%m-%d %H:%M UTC"), "seconds": round(seconds, 1)}
    if llm is not None:
        meta.update(model=settings.model, effort=settings.effort, usage=llm.usage,
                    cost_usd=estimate_cost(settings.model, llm.usage))

    case_reports = []
    for case, (res, extracted, secs) in zip(cases, outcomes):
        gold_by_id = {g.id: g for g in case.requirements}
        case_reports.append({
            "id": case.id, "title": case.title, "source": case.source, "error": res.error,
            "seconds": round(secs, 1), "gold": res.gold_total, "found": len(res.matched), "recall": round(res.recall, 4),
            "mandatory_found": res.mandatory_found, "mandatory_total": res.mandatory_total,
            "extracted": res.extracted_total,
            "missed": [{"id": g, "kind": gold_by_id[g].kind, "mandatory": gold_by_id[g].mandatory,
                        "quote": gold_by_id[g].quote} for g in res.missed],
            "trap_hits": res.trap_hits,
            "unmatched_extracted": [{"kind": extracted[i].kind, "page": extracted[i].page, "text": extracted[i].text}
                                    for i in res.unmatched_extracted],
            "matches": [{"gold": g, "kind": extracted[ei].kind, "page": extracted[ei].page, "score": sc}
                        for g, ei, sc in res.matched],
        })

    report = {"meta": meta, "summary": summary, "cases": case_reports}
    args.out.mkdir(parents=True, exist_ok=True)
    stem = started.strftime("%Y%m%d-%H%M%S") + f"-{args.runner}" + (f"-{settings.model}" if llm else "")
    (args.out / f"{stem}.json").write_text(json.dumps(report, indent=2) + "\n")
    md = to_markdown(report)
    (args.out / f"{stem}.md").write_text(md)
    print(md)
    print(f"Saved {args.out / stem}.json and .md")

    if args.min_recall is not None and summary["recall"] < args.min_recall:
        print(f"FAIL: recall {summary['recall']:.1%} is below {args.min_recall:.0%}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
