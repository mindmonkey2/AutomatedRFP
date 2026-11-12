"""Regression tests for the 2026-11 audit fixes: deletes, login limiting, page markers,
file processing order and Word table order."""

import io
from pathlib import Path

import docx
from sqlalchemy import select, text
from starlette.requests import Request

from app import jobs, pipeline
from app.auth import _RateLimiter, client_ip
from app.config import settings
from app.db import worker_session
from app.models import Job
from app.parsing import parse_file, windows

BASE = b"[Page 1]\nThe bidder shall submit three hard copies.\nThe bidder shall describe its K-12 experience.\n"
ADDENDUM = b"ADDENDUM 1\nA 10% bid bond is now required.\n"


def _stored_files() -> set[Path]:
    return {p for p in settings.storage_dir.rglob("*") if p.is_file()}


def _upload(client, bid_id, name, data, kind):
    r = client.post(f"/bids/{bid_id}/files", files={"file": (name, data, "text/plain")}, data={"kind": kind})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- deletes


def test_delete_bid_with_addendum_removes_rows_and_files(client):
    before = _stored_files()
    bid = client.post("/bids", json={"title": "Delete me"}).json()
    _upload(client, bid["id"], "rfp.txt", BASE, "base")
    _upload(client, bid["id"], "add1.txt", ADDENDUM, "addendum")
    reqs = client.get(f"/bids/{bid['id']}/requirements").json()
    assert any(r["change_type"] == "modified" for r in reqs)  # a requirement points at the addendum
    assert len(_stored_files() - before) == 2

    assert client.delete(f"/bids/{bid['id']}").status_code == 204
    assert client.get(f"/bids/{bid['id']}").status_code == 404
    assert _stored_files() - before == set()


def test_delete_library_document_removes_file(client):
    before = _stored_files()
    doc = client.post("/library/documents", files={"file": ("past.txt", b"We built a school.", "text/plain")}).json()
    assert len(_stored_files() - before) == 1
    assert client.delete(f"/library/documents/{doc['id']}").status_code == 204
    assert _stored_files() - before == set()


# ---------------------------------------------------------------- login limiting


def _request(peer: str, forwarded: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "client": (peer, 5000), "headers": headers})


def test_client_ip_behind_the_bundled_proxy(monkeypatch):
    monkeypatch.setattr(settings, "forwarded_hops", 0)
    assert client_ip(_request("203.0.113.9")) == "203.0.113.9"
    # Through the Next.js proxy on this machine every visitor shares 127.0.0.1, and the
    # X-Forwarded-For it passes on can be forged, so no per-address key is used at all.
    assert client_ip(_request("127.0.0.1", "198.51.100.1")) is None
    assert client_ip(_request("::1")) is None


def test_client_ip_with_a_trusted_reverse_proxy(monkeypatch):
    monkeypatch.setattr(settings, "forwarded_hops", 1)
    # The visitor forged the first entry; nginx appended the real address last.
    assert client_ip(_request("127.0.0.1", "10.0.0.1, 198.51.100.7")) == "198.51.100.7"
    assert client_ip(_request("127.0.0.1")) == "127.0.0.1"


def test_failed_logins_by_others_do_not_lock_out_a_user(anon, monkeypatch):
    from tests.conftest import PASSWORD, signup

    user = signup(anon)
    anon.post("/auth/logout")
    monkeypatch.setattr("app.auth.client_ip", lambda request: None)  # as behind the bundled proxy
    for i in range(12):
        anon.post("/auth/login", json={"email": f"stranger{i}@example.com", "password": "wrong-password"})
    r = anon.post("/auth/login", json={"email": user["email"], "password": PASSWORD})
    assert r.status_code == 200, r.text


def test_rate_limiter_memory_is_bounded(monkeypatch):
    lim = _RateLimiter(limit=3, window_s=60)
    for i in range(100):
        assert not lim.blocked(f"email:{i}@example.com")
    assert lim.hits == {}  # lookups do not create entries

    monkeypatch.setattr(_RateLimiter, "MAX_KEYS", 10)
    clock = [1000.0]
    monkeypatch.setattr("app.auth.time.monotonic", lambda: clock[0])
    for i in range(10):
        lim.fail(f"old{i}")
    clock[0] += 120  # the old failures expire
    lim.fail("new")
    assert set(lim.hits) == {"new"}


# ---------------------------------------------------------------- extraction windows


def test_windows_starting_mid_page_carry_the_page_marker():
    page2 = "\n\n".join(f"Paragraph {i}: the contractor shall do item {i}." for i in range(200))
    text = "[Page 1]\nIntro.\n\n[Page 2]\n" + page2
    ws = windows(text, 2000)
    assert len(ws) > 2
    for w in ws[1:]:
        assert w.startswith("[Page 2]"), w[:40]
    # Nothing lost: every paragraph is in exactly one window.
    joined = "".join(w.split("\n", 1)[1] if w.startswith("[Page 2] (continued)") else w for w in ws)
    assert all(f"Paragraph {i}:" in joined for i in range(200))


# ---------------------------------------------------------------- processing order


def test_addendum_waits_for_the_base_file(client):
    bid = client.post("/bids", json={"title": "Order"}).json()
    client.run_jobs = False  # leave both jobs queued
    base = _upload(client, bid["id"], "rfp.txt", BASE, "base")
    add = _upload(client, bid["id"], "add1.txt", ADDENDUM, "addendum")
    assert add["sequence"] == base["sequence"] + 1

    # Hold the base file's job back, so a worker picks up the addendum first: it must wait.
    with worker_session() as s:
        s.execute(text("UPDATE jobs SET run_after = now() + interval '1 hour' "
                       "WHERE kind = 'process_file' AND target_id = :id"), {"id": base["id"]})
        s.commit()
    assert jobs.run_until_idle() == 1  # the addendum ran, and deferred itself
    files = client.get(f"/bids/{bid['id']}").json()["files"]
    assert [f["status"] for f in files] == ["queued", "queued"]
    assert "Waiting" in files[1]["progress"]
    with worker_session() as s:
        add_job = s.scalar(select(Job).where(Job.kind == "process_file", Job.target_id == add["id"]))
        assert add_job.status == "queued" and add_job.attempts == 0  # waiting does not use up an attempt

    # Release the base job: it runs now; the addendum's retry is due a few seconds later.
    with worker_session() as s:
        s.execute(text("UPDATE jobs SET run_after = now() WHERE kind = 'process_file' AND target_id = :id"),
                  {"id": base["id"]})
        s.commit()
    assert jobs.run_until_idle() == 1  # only the base is due
    assert jobs.run_until_idle(ahead_s=30) == 1  # then the addendum, applied as an addendum
    files = client.get(f"/bids/{bid['id']}").json()["files"]
    assert [f["status"] for f in files] == ["ready", "ready"]
    assert files[1]["change_summary"] and files[1]["progress"] is None
    reqs = client.get(f"/bids/{bid['id']}/requirements").json()
    assert len(reqs) == 3 and {r["change_type"] for r in reqs} >= {"added", "modified"}

    # Running the addendum's handler again (a duplicate delivery) changes nothing.
    pipeline.process_solicitation_file(client.user["org_id"], add["id"])
    assert len(client.get(f"/bids/{bid['id']}/requirements").json()) == 3


# ---------------------------------------------------------------- Word tables


def test_docx_tables_stay_under_their_heading(tmp_path):
    d = docx.Document()
    d.add_heading("Section 1 Documents to submit", 1)
    t = d.add_table(rows=2, cols=3)
    t.cell(0, 0).merge(t.cell(0, 1))
    t.cell(0, 0).text, t.cell(0, 2).text = "Document", "Required"
    t.cell(1, 0).text, t.cell(1, 1).text, t.cell(1, 2).text = "Yes", "Yes", "Copy of EMD"
    d.add_heading("Section 2 Evaluation", 1)
    buf = io.BytesIO()
    d.save(buf)
    (tmp_path / "t.docx").write_bytes(buf.getvalue())

    text = parse_file(tmp_path / "t.docx").pages[0].text
    assert text.index("Copy of EMD") < text.index("Section 2")
    assert "Document | Required" in text  # merged cell once
    assert "Yes | Yes | Copy of EMD" in text  # equal neighbouring cells kept
