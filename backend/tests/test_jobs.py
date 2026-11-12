"""The durable job queue: atomic enqueue, retries, permanent failures, crash recovery,
heartbeats, tenant isolation and real worker threads."""

import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app import jobs
from app.config import settings
from app.db import SessionLocal, org_session, worker_session
from app.llm import LLMError
from app.main import app
from app.models import Job

RFP = b"[Page 1]\nThe bidder shall describe its K-12 experience.\nThe bidder shall submit two copies.\n"


def _job(kind: str, target_id: int) -> Job:
    with worker_session() as s:
        return s.scalar(select(Job).where(Job.kind == kind, Job.target_id == target_id).order_by(Job.id.desc()))


def _upload(client, data=RFP):
    bid = client.post("/bids", json={"title": "Queue test"}).json()
    f = client.post(f"/bids/{bid['id']}/files", files={"file": ("rfp.txt", data, "text/plain")},
                    data={"kind": "base"}).json()
    return bid, f


def _file(client, bid):
    return client.get(f"/bids/{bid['id']}").json()["files"][0]


def test_upload_saves_its_job_in_the_same_transaction(client):
    client.run_jobs = False
    bid, f = _upload(client)
    job = _job("process_file", f["id"])
    assert job.status == "queued" and job.org_id == client.user["org_id"] and job.attempts == 0
    assert _file(client, bid)["status"] == "queued"


def test_only_one_live_job_per_target(client):
    client.run_jobs = False
    _, f = _upload(client)
    with org_session(client.user["org_id"]) as s:
        jobs.enqueue(s, client.user["org_id"], "process_file", f["id"])  # e.g. a double click
        s.commit()
    with worker_session() as s:
        n = s.scalar(select(text("count(*)")).select_from(Job).where(Job.target_id == f["id"],
                                                                     Job.kind == "process_file"))
    assert n == 1


def test_temporary_failure_is_retried_then_succeeds(client, fake_llm, monkeypatch):
    calls = {"n": 0}
    real = fake_llm.extract_requirements

    def flaky(text_):
        calls["n"] += 1
        if calls["n"] == 1:
            raise LLMError("Could not reach the model server: connection refused", retryable=True)
        return real(text_)

    monkeypatch.setattr(fake_llm, "extract_requirements", flaky)
    bid, f = _upload(client)
    after_first = _file(client, bid)
    assert after_first["status"] == "queued" and after_first["error"] is None
    assert "temporary problem" in after_first["progress"] and "Trying again" in after_first["progress"]
    job = _job("process_file", f["id"])
    assert job.status == "queued" and job.attempts == 1 and "connection refused" in job.last_error

    assert jobs.run_until_idle(ahead_s=settings.job_retry_base_s + 5) == 1  # the retry, once it is due
    assert _file(client, bid)["status"] == "ready"
    assert len(client.get(f"/bids/{bid['id']}/requirements").json()) == 2
    assert _job("process_file", f["id"]).status == "done"


def test_permanent_failure_is_not_retried(client, fake_llm, monkeypatch):
    def bad_key(_text):
        raise LLMError("Claude API key was rejected. Check ANTHROPIC_API_KEY in backend/.env.")

    monkeypatch.setattr(fake_llm, "extract_requirements", bad_key)
    bid, f = _upload(client)
    file = _file(client, bid)
    assert file["status"] == "failed" and "API key" in file["error"]
    job = _job("process_file", f["id"])
    assert job.status == "failed" and job.attempts == 1


def test_gives_up_after_max_attempts(client, fake_llm, monkeypatch):
    def down(_text):
        raise LLMError("Model server error 503: overloaded", retryable=True)

    monkeypatch.setattr(fake_llm, "extract_requirements", down)
    bid, f = _upload(client)
    jobs.run_until_idle(ahead_s=10_000)  # run both retries
    file = _file(client, bid)
    assert file["status"] == "failed" and "503" in file["error"]
    job = _job("process_file", f["id"])
    assert job.status == "failed" and job.attempts == settings.job_max_attempts


def test_job_of_a_crashed_worker_is_taken_over(client):
    client.run_jobs = False
    bid, f = _upload(client)
    job = jobs.claim(worker="crashed-host:1")  # claimed, then the worker died without finishing
    assert job.target_id == f["id"]
    with worker_session() as s:
        s.execute(text("UPDATE jobs SET heartbeat_at = now() - interval '1 hour' WHERE id = :id"), {"id": job.id})
        s.commit()
    assert jobs.reap() == 1
    assert _job("process_file", f["id"]).status == "queued"
    jobs.run_until_idle()
    assert _file(client, bid)["status"] == "ready"


def test_repeatedly_crashing_job_is_marked_failed_on_the_file(client, monkeypatch):
    client.run_jobs = False
    monkeypatch.setattr(settings, "job_max_attempts", 1)
    bid, _ = _upload(client)
    job = jobs.claim(worker="crashed-host:1")
    with worker_session() as s:
        s.execute(text("UPDATE jobs SET heartbeat_at = now() - interval '1 hour' WHERE id = :id"), {"id": job.id})
        s.commit()
    jobs.reap()
    file = _file(client, bid)
    assert file["status"] == "failed" and "stopped repeatedly" in file["error"]


def test_heartbeat_keeps_a_long_job_alive(client, monkeypatch):
    monkeypatch.setattr(settings, "job_lease_s", 0.6)
    started, release = threading.Event(), threading.Event()

    def slow(org_id, target_id, job):
        started.set()
        release.wait(5)

    jobs.register("test_slow", slow, lambda *a: None)
    with org_session(client.user["org_id"]) as s:
        jobs.enqueue(s, client.user["org_id"], "test_slow", 1)
        s.commit()
    t = threading.Thread(target=jobs.run_until_idle)
    t.start()
    assert started.wait(5)
    time.sleep(1.5)  # well past the lease: only the heartbeat keeps the job ours
    assert jobs.reap() == 0
    release.set()
    t.join(5)
    assert _job("test_slow", 1).status == "done"
    del jobs.HANDLERS["test_slow"]


def test_jobs_are_isolated_between_organizations(fake_llm):
    with TestClient(app) as a, TestClient(app) as b:
        from tests.conftest import _run_jobs_after, signup

        for c in (a, b):
            _run_jobs_after(c).run_jobs = False
            c.user = signup(c)
        _upload(a)
        _upload(b)
        with org_session(a.user["org_id"]) as s:
            seen = {j.org_id for j in s.scalars(select(Job))}
        assert seen == {a.user["org_id"]}
        with SessionLocal() as s:  # no organization bound and not the worker: sees nothing
            assert s.scalars(select(Job)).all() == []
        with worker_session() as s:
            assert {a.user["org_id"], b.user["org_id"]} <= {j.org_id for j in s.scalars(select(Job))}
        jobs.run_until_idle()


def test_drafting_queues_one_job_per_answer_and_respects_later_edits(client):
    bid, _ = _upload(client)
    client.run_jobs = False
    queued = client.post(f"/bids/{bid['id']}/draft", json={}).json()["queued"]
    assert len(queued) == 1
    req = client.get(f"/bids/{bid['id']}/requirements").json()
    ans = next(r for r in req if r["id"] == queued[0])["answer"]
    assert ans["status"] == "queued" and _job("draft_answer", queued[0]).status == "queued"

    # The reviewer writes the answer by hand before the worker gets to it: the job must not overwrite it.
    client.patch(f"/answers/{ans['id']}", json={"final_text": "Written by hand.", "status": "accepted"})
    jobs.run_until_idle()
    req = client.get(f"/bids/{bid['id']}/requirements").json()
    ans = next(r for r in req if r["id"] == queued[0])["answer"]
    assert ans["status"] == "accepted" and ans["final_text"] == "Written by hand."


def test_worker_threads_process_the_queue(client):
    client.run_jobs = False
    bids = [_upload(client)[0] for _ in range(3)]
    worker = jobs.Worker(threads=2).start()
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and any(_file(client, b)["status"] != "ready" for b in bids):
            time.sleep(0.2)
    finally:
        worker.stop(wait_s=10)
    assert [_file(client, b)["status"] for b in bids] == ["ready"] * 3


@pytest.mark.parametrize("status,temporary", [(503, True), (429, True), (401, False), (400, False)])
def test_openai_compatible_errors_are_classified(status, temporary, monkeypatch):
    import httpx

    from app.llm_openai import OpenAICompatibleLLM

    monkeypatch.setattr(settings, "openai_model", "m")
    client = httpx.Client(base_url="http://x/v1",
                          transport=httpx.MockTransport(lambda r: httpx.Response(status, json={"error": "e"})))
    llm = OpenAICompatibleLLM(client=client)
    llm.mode = "prompt"  # skip the structured-output fallback path
    with pytest.raises(LLMError) as e:
        llm.extract_requirements("text")
    assert jobs.is_temporary(e.value) is temporary
