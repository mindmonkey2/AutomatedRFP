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


# ---------------------------------------------------------------- obligation sweep (Indian tender styles)


def _sweep(text: str) -> list[str]:
    return [s for _, s in obligation_sentences("[Page 1]\n" + text)]


def test_sweep_joins_pdf_hard_wraps():
    text = ("The contractor must be enlisted with the State PWD and must also furnish self attested copies \n"
            "of PAN, GST and EPF registration with the bid.")
    assert _sweep(text) == ["The contractor must be enlisted with the State PWD and must also furnish self "
                            "attested copies of PAN, GST and EPF registration with the bid."]


def test_sweep_joins_one_word_per_line_layout():
    assert _sweep("(i) Bidder \nshall \ncomply \nwith \nthe \nIntegrity Pact.") == [
        "Bidder shall comply with the Integrity Pact."]


def test_sweep_indian_wording():
    found = _sweep("(i) The bidder should have completed three similar works in the last seven years.\n\n"
                   "(ii) An affidavit to be enclosed that the firm is not blacklisted.\n\n"
                   "(iii) Conditional bids will not to be accepted.\n\n"
                   "(iv) Bidders have to pay Rs. 5,000/- as tender fee.")
    assert len(found) == 4
    assert found[3] == "Bidders have to pay Rs. 5,000/- as tender fee."  # no split at "Rs."


def test_sweep_document_checklist_without_obligation_words():
    text = ("Documents to be uploaded with the technical bid:\n\n"
            "1. \nCopy of EMD.\n\n2. \nLetter of Transmittal.\n\n"
            "(c) if applicable, Power of Attorney for the lead partner;\n\n"
            "Contact us for help.")
    found = _sweep(text)
    assert {"Copy of EMD.", "Letter of Transmittal.",
            "if applicable, Power of Attorney for the lead partner;"} <= set(found)
    assert "Contact us for help." not in found


def test_sweep_items_under_an_invalid_if_lead_in():
    text = ("The bid shall become invalid if:\n\n"
            "1. The bidder does not upload the GST certificate.\n\n"
            "2. The bid is received after the due time.\n\n"
            "The weather in the region is mild.")
    found = _sweep(text)
    assert "The bidder does not upload the GST certificate." in found
    assert "The bid is received after the due time." in found
    assert "The weather in the region is mild." not in found


def test_sweep_summary_table_label_and_value():
    text = ("Estimated Cost \nRs 12,00,000 \nLast Date & Time of Bid submission. \n15.03.2026, 3.00 PM \n"
            "Period of Completion \n9 Months \nName of Work \nRepairs to hostel block")
    found = _sweep(text)
    assert "Last Date & Time of Bid submission. 15.03.2026, 3.00 PM" in found
    assert "Period of Completion 9 Months" in found
    assert not any("Estimated Cost" in s or "Name of Work" in s for s in found)


def test_sweep_keeps_inline_lists_with_their_obligation():
    text = "The Contractor shall be required to \n(a) \nstart work within 10 days, (b) finish within 90 days."
    assert _sweep(text) == ["The Contractor shall be required to (a) start work within 10 days, "
                            "(b) finish within 90 days."]


def test_sweep_skips_authority_obligations():
    found = _sweep("The Authority shall open the bids at 3 PM.\n\n"
                   "The Department reserves the right to reject any bid.\n\n"
                   "Financial bids shall be opened only for qualified bidders.\n\n"
                   "The bidder shall submit a bid security.")
    assert found == ["The bidder shall submit a bid security."]
