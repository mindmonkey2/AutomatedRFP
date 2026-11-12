import json

import anthropic
import httpx2

from app.llm import ClaudeLLM, ExtractionResult
from app.parsing import Page, chunk_pages, obligation_sentences, windows
from app.pipeline import quote_in, score, strip_markers


def test_chunker_keeps_pages_and_headings():
    pages = [Page(1, "1. INTRODUCTION\n\nThe owner seeks bids.\n\n2. SCOPE OF WORK\n\nBuild a school.")]
    chunks = chunk_pages(pages, max_chars=40)
    assert [c.heading for c in chunks] == ["1. INTRODUCTION", "2. SCOPE OF WORK"]
    assert all(c.page == 1 for c in chunks)


def test_chunker_splits_long_paragraphs():
    long = ". ".join(["This sentence is filler text"] * 200)
    chunks = chunk_pages([Page(None, long)], max_chars=500)
    assert len(chunks) > 5 and all(len(c.text) <= 500 for c in chunks)


def test_windows_cover_all_text():
    text = "".join(f"\n[Page {i}]\n" + "x" * 900 for i in range(1, 30))
    ws = windows(text, 5000)
    assert "".join(ws) == text and all(len(w) <= 5000 for w in ws)


def test_obligation_sweep_finds_pages():
    found = obligation_sentences("[Page 3]\nBidders must include a signed Form W-9 with the bid package.")
    assert found == [(3, "Bidders must include a signed Form W-9 with the bid package.")]


def test_quote_verification():
    src = "Our firm built Riverside Elementary School, a 60,000 sq ft facility, in 2023."
    assert quote_in("built Riverside Elementary School", src)
    assert quote_in("Riverside Elementary School ... sq ft facility", src)
    assert not quote_in("built Lakeside High School", src)
    assert not quote_in("in", src)  # too short to count


def test_score_penalises_unverified_and_unsupported():
    good, _ = score(0.9, 2, 2, [], 5)
    bad, reasons = score(0.9, 2, 1, ["EMR rating"], 5)
    none, _ = score(0.9, 0, 0, [], 0)
    assert good > bad > none and none <= 0.2
    assert len(reasons) == 2


def test_strip_markers():
    assert strip_markers("Built in 2023 [1]. Also [2, 3] here.") == "Built in 2023. Also here."


def test_claude_request_shape():
    """Checks the real SDK call (model, caching, structured output, effort, fallbacks) without network."""
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta", "")
        payload = {"summary": "s", "requirements": []}
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": seen["body"]["model"],
            "content": [{"type": "text", "text": json.dumps(payload)}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        })

    client = anthropic.Anthropic(
        api_key="test", http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler))
    )
    result = ClaudeLLM(client).extract_requirements("[Page 1]\nThe bidder shall submit a bond.")
    assert isinstance(result, ExtractionResult)
    body = seen["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"]["effort"] == "high"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["beta"]
