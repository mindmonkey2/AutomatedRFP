"""The evaluation harness: answer keys are valid, matching is strict, and the Claude path runs."""

import json

from app.llm import ExtractedRequirement, ExtractionResult
from evals import extraction
from evals.dataset import load_cases, validate
from evals.scoring import coverage, score_case


def req(quote: str, kind: str = "submission", page: int | None = 1, text: str | None = None) -> ExtractedRequirement:
    return ExtractedRequirement(text=text or quote, kind=kind, section=None, page=page, source_quote=quote,
                                mandatory=True, needs_response=False, page_limit=None)


def test_answer_keys_are_valid():
    cases = load_cases()
    assert len(cases) >= 8
    assert sum(len(c.requirements) for c in cases) >= 180
    for c in cases:
        assert validate(c) == [], c.id
        assert c.labelled_by, f"{c.id}: record who labelled the answer key"


def test_real_cases_cite_their_public_source():
    real = [c for c in load_cases() if c.source == "real"]
    assert len(real) >= 3
    for c in real:
        assert c.source_url and c.source_url.startswith("https://"), c.id


def test_perfect_extraction_scores_100_percent():
    for case in load_cases():
        perfect = [req(g.quote, g.kind, g.page) for g in case.requirements]
        res = score_case(case, perfect)
        assert res.recall == 1.0, (case.id, res.missed)
        assert res.kind_correct == len(case.requirements)
        assert res.trap_hits == [] and res.unmatched_extracted == []


def test_merged_requirements_only_count_once():
    case = next(c for c in load_cases() if c.id == "k12_school_ifb")
    forms = [g for g in case.requirements if g.id in ("R10", "R11", "R12", "R13")]
    merged = req("Submit: " + "; ".join(g.quote for g in forms), "form", 2)
    res = score_case(case, [merged])
    assert len(res.matched) == 1  # one merged item hides three forms from the checklist


def test_unrelated_text_does_not_match_and_traps_are_counted():
    case = next(c for c in load_cases() if c.id == "water_main_srf_ifb")
    trap = case.traps[0].quote
    res = score_case(case, [req("The contractor shall keep the site tidy."), req(trap)])
    assert res.matched == []
    assert res.trap_hits == [trap]
    assert coverage("bid bond of five percent", req("A bid bond of five percent (5%) is required")) == 1.0


def test_keyword_baseline_runs(tmp_path):
    assert extraction.main(["--runner", "keyword", "--out", str(tmp_path)]) == 0
    report = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert 0.3 < report["summary"]["recall"] < 0.9
    assert (tmp_path / next(tmp_path.glob("*.md")).name).read_text().startswith("# Requirement extraction eval")


class _GoldEchoLLM:
    """Stand-in model that 'extracts' the gold quotes present in each window."""

    def __init__(self):
        self.gold = [g for c in load_cases() for g in c.requirements]
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}

    def extract_requirements(self, text):
        self.usage["calls"] += 1
        self.usage["input_tokens"] += 1000
        self.usage["output_tokens"] += 200
        flat = " ".join(text.split())
        found = [req(g.quote, g.kind, g.page) for g in self.gold if g.quote in flat]
        return ExtractionResult(summary="s", requirements=found)

    def fill_gaps(self, sentences):
        return ExtractionResult(summary="", requirements=[])


def test_claude_runner_path_with_stand_in_model(tmp_path, monkeypatch):
    from app.pipeline import extract_from_text

    fake = _GoldEchoLLM()
    monkeypatch.setattr(extraction, "make_claude_runner",
                        lambda: ((lambda case: extract_from_text(case.document, fake)[1]), fake))
    code = extraction.main(["--model", "claude-opus-5-5", "--out", str(tmp_path), "--min-recall", "0.95"])
    assert code == 0
    report = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert report["summary"]["recall"] == 1.0
    assert report["meta"]["cost_usd"] > 0  # usage is priced
