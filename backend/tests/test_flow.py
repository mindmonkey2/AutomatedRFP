"""End-to-end API flow with a fake LLM: library -> RFP -> matrix -> draft -> review -> export."""

import io
from datetime import date, timedelta

import docx
import openpyxl
import pymupdf


def make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


def wait_ready(client, url, key="status"):
    # TestClient runs background tasks before returning, so one read is enough.
    return client.get(url).json()


def test_full_flow(client):
    h = {}  # the client fixture is already signed in

    # 1. Library: a past proposal (PDF), a project record and an expiring credential.
    pdf = make_pdf([
        "Past Proposal - Riverside Elementary\n\nOur firm built Riverside Elementary School, a 60,000 sq ft K-12\n"
        "facility for Riverside Unified, completed on schedule in 2023.",
    ])
    r = client.post("/library/documents", headers=h, files={"file": ("riverside.pdf", pdf, "application/pdf")},
                    data={"doc_type": "proposal"})
    assert r.status_code == 201, r.text
    docs = client.get("/library/documents", headers=h).json()
    assert docs[0]["status"] == "ready" and docs[0]["chunk_count"] >= 1

    r = client.post("/projects", headers=h, json={"name": "Oak Hill Middle School", "client": "Oak Hill ISD",
                                                  "sector": "public-k12", "contract_value": 18500000,
                                                  "scope": "New 3-story K-12 middle school"})
    assert r.status_code == 201
    soon = (date.today() + timedelta(days=10)).isoformat()
    r = client.post("/credentials", headers=h, json={"kind": "insurance", "name": "General liability",
                                                     "number": "GL-123", "expires_on": soon})
    assert r.json()["days_to_expiry"] == 10
    assert len(client.get("/credentials/expiring", headers=h).json()) == 1

    hits = client.get("/library/search", headers=h, params={"q": "K-12 school experience"}).json()
    assert {x["source_type"] for x in hits} >= {"document", "project"}

    # 2. Bid + solicitation -> compliance matrix.
    bid = client.post("/bids", headers=h, json={"title": "Maple Elementary Replacement", "agency": "Maple USD"}).json()
    rfp = make_pdf([
        "INVITATION FOR BIDS\n\nThe bidder shall submit three hard copies.",
        "The bidder shall describe its experience building K-12 schools.",
    ])
    r = client.post(f"/bids/{bid['id']}/files", headers=h, files={"file": ("rfp.pdf", rfp, "application/pdf")},
                    data={"kind": "base"})
    assert r.status_code == 201
    b = client.get(f"/bids/{bid['id']}", headers=h).json()
    assert b["files"][0]["status"] == "ready", b["files"][0]["error"]
    assert b["summary"]
    reqs = client.get(f"/bids/{bid['id']}/requirements", headers=h).json()
    assert len(reqs) == 2
    question = next(x for x in reqs if x["needs_response"])
    assert question["page"] == 2

    # 3. Draft: only response items are drafted; citations verified against the source.
    r = client.post(f"/bids/{bid['id']}/draft", headers=h, json={})
    assert r.status_code == 202 and r.json()["queued"] == [question["id"]]
    reqs = client.get(f"/bids/{bid['id']}/requirements", headers=h).json()
    ans = next(x for x in reqs if x["id"] == question["id"])["answer"]
    assert ans["status"] == "drafted", ans
    assert ans["citations"][0]["verified"] is True
    assert ans["confidence"] >= 0.6

    # Re-drafting without force does not overwrite existing work.
    assert client.post(f"/bids/{bid['id']}/draft", headers=h, json={}).json()["queued"] == []

    # 4. Readiness flags the unreviewed answer and the un-met submission item.
    ready = client.get(f"/bids/{bid['id']}/readiness", headers=h).json()
    assert not ready["ready"] and ready["unreviewed_ids"] == [question["id"]]

    # 5. Review: edit + approve -> answer becomes a library passage.
    r = client.patch(f"/answers/{ans['id']}", headers=h, json={"final_text": "Edited answer about Riverside [1]."})
    assert r.json()["final_text"].startswith("Edited")
    r = client.post(f"/answers/{ans['id']}/approve", headers=h)
    assert r.json()["status"] == "approved"
    hits = client.get("/library/search", headers=h, params={"q": "Edited Riverside"}).json()
    assert any(x["source_type"] == "answer" for x in hits)

    # 6. Addendum: modifies the question (answer goes stale) and adds a bond requirement.
    add = make_pdf(["ADDENDUM 1\n\nA 10% bid bond is now required."])
    client.post(f"/bids/{bid['id']}/files", headers=h, files={"file": ("add1.pdf", add, "application/pdf")},
                data={"kind": "addendum"})
    b = client.get(f"/bids/{bid['id']}", headers=h).json()
    assert b["files"][1]["change_summary"].startswith("Due date moved")
    reqs = client.get(f"/bids/{bid['id']}/requirements", headers=h).json()
    assert len(reqs) == 3
    assert {x["change_type"] for x in reqs} >= {"added", "modified"}

    # 7. Exports.
    r = client.get(f"/bids/{bid['id']}/export/response.docx", headers=h)
    assert r.status_code == 200
    text = "\n".join(p.text for p in docx.Document(io.BytesIO(r.content)).paragraphs)
    assert "Edited answer about Riverside." in text and "[1]" not in text
    r = client.get(f"/bids/{bid['id']}/export/matrix.xlsx", headers=h)
    ws = openpyxl.load_workbook(io.BytesIO(r.content)).active
    assert ws.max_row == 4  # header + 3 requirements


def test_rejects_unsupported_upload(client):
    r = client.post("/library/documents", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415
