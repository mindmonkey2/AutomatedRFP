"""Search by meaning: embedding jobs, hybrid ranking, fallbacks, tenant isolation."""

import math
import re
import zlib

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app import embeddings, jobs, retrieval
from app.config import settings
from app.db import org_session, worker_session
from app.llm import LLMError
from app.main import app
from app.models import Chunk, Job
from app.retrieval import Hit

# A toy "meaning": words map to a concept, concepts to vector dimensions. Enough to show that a
# passage sharing no words with the question is still found, without downloading a real model.
CONCEPTS = {
    "pupil": "student", "pupils": "student", "student": "student", "students": "student", "learners": "student",
    "literacy": "reading", "reading": "reading",
    "revenue": "turnover", "turnover": "turnover", "income": "turnover",
    "injury": "safety", "injuries": "safety", "safety": "safety", "accident": "safety", "incident": "safety",
}
DIM = 32


class FakeEmbedder:
    def __init__(self, model="fake-embed-v1", fail=False):
        self.model, self.fail, self.calls = model, fail, 0

    def _vec(self, t: str) -> list[float]:
        v = [0.0] * DIM
        for w in re.findall(r"[a-z]+", t.lower()):
            v[zlib.crc32(CONCEPTS.get(w, w).encode()) % DIM] += 1
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_documents(self, texts):
        self.calls += 1
        if self.fail:
            raise LLMError("Could not reach the embeddings server", retryable=True)
        return [self._vec(t) for t in texts]

    def embed_query(self, t):
        if self.fail:
            raise LLMError("Could not reach the embeddings server", retryable=True)
        return self._vec(t)


@pytest.fixture
def fake_embedder(monkeypatch):
    fake = FakeEmbedder()
    monkeypatch.setattr(settings, "embedding_provider", "local")  # anything but "none" turns it on
    embeddings.set_embedder(fake)
    yield fake
    embeddings.set_embedder(None)


def _doc(client, name, body):
    r = client.post("/library/documents", files={"file": (name, body.encode(), "text/plain")})
    assert r.status_code == 201
    return r.json()


def _count_embeddings(org_id, model="fake-embed-v1"):
    with org_session(org_id) as s:
        return s.execute(text("SELECT count(*) FROM chunk_embeddings WHERE model = :m"), {"m": model}).scalar()


def test_library_passages_are_embedded_in_the_background(client, fake_embedder):
    _doc(client, "reading.txt", "Our tutoring program raised students' reading scores by two grade levels.")
    client.post("/projects", json={"name": "Oak Hill Middle School", "scope": "New classrooms for 900 students"})
    org = client.user["org_id"]
    with org_session(org) as s:
        n_chunks = s.scalar(select(text("count(*)")).select_from(Chunk))
    assert n_chunks == 2 and _count_embeddings(org) == 2
    with worker_session() as s:  # one queued job per organization covered both additions
        assert {j.status for j in s.scalars(select(Job).where(Job.kind == "embed_library", Job.target_id == org))} == {"done"}


def test_hybrid_search_finds_passages_worded_differently(client, fake_embedder):
    _doc(client, "reading.txt", "Our tutoring program raised students' reading scores by two grade levels.")
    _doc(client, "fleet.txt", "We maintain a fleet of 40 excavators and 12 cranes.")
    q = "pupil literacy"
    with org_session(client.user["org_id"]) as s:
        assert retrieval.keyword_search(s, client.user["org_id"], q) == []  # no shared words
    hits = client.get("/library/search", params={"q": q}).json()
    assert hits and hits[0]["label"] == "reading.txt"


def test_keyword_and_meaning_agreeing_rank_first(client, fake_embedder):
    _doc(client, "a.txt", "Annual turnover for the last three years: Rs. 46.29 lakh.")
    _doc(client, "b.txt", "Average annual revenue grew steadily.")
    _doc(client, "c.txt", "Three years of crane operations.")
    hits = client.get("/library/search", params={"q": "annual turnover"}).json()
    assert [h["label"] for h in hits[:2]] == ["a.txt", "b.txt"]


def test_search_falls_back_to_keywords_when_embeddings_fail(client, fake_embedder):
    _doc(client, "safety.txt", "Our safety record: zero lost-time incidents in 2024.")
    fake_embedder.fail = True
    hits = client.get("/library/search", params={"q": "safety record"}).json()
    assert [h["label"] for h in hits] == ["safety.txt"]


def test_embedding_failure_is_retried_and_does_not_block_ingest(client, fake_embedder):
    fake_embedder.fail = True
    _doc(client, "safety.txt", "Zero lost-time incidents in 2024.")
    assert client.get("/library/documents").json()[0]["status"] == "ready"  # the document itself is fine
    with worker_session() as s:
        job = s.scalar(select(Job).where(Job.kind == "embed_library", Job.target_id == client.user["org_id"]))
        assert job.status == "queued" and job.attempts == 1  # will be retried later
    fake_embedder.fail = False
    jobs.run_until_idle(ahead_s=settings.job_retry_base_s + 5)
    assert _count_embeddings(client.user["org_id"]) == 1


def test_switching_models_re_embeds_everything(client, fake_embedder):
    _doc(client, "a.txt", "We built three schools.")
    org = client.user["org_id"]
    fake_embedder.model = "fake-embed-v2"
    with org_session(org) as s:
        embeddings.enqueue_embedding(s, org)
        s.commit()
    jobs.run_until_idle()
    assert _count_embeddings(org, "fake-embed-v1") == 1 and _count_embeddings(org, "fake-embed-v2") == 1


def test_deleting_a_document_deletes_its_vectors(client, fake_embedder):
    doc = _doc(client, "a.txt", "We built three schools.")
    assert _count_embeddings(client.user["org_id"]) == 1
    client.delete(f"/library/documents/{doc['id']}")
    assert _count_embeddings(client.user["org_id"]) == 0


def test_vectors_are_isolated_between_organizations(fake_llm, fake_embedder):
    from tests.conftest import _run_jobs_after, signup

    with TestClient(app) as a, TestClient(app) as b:
        for c in (a, b):
            _run_jobs_after(c)
            c.user = signup(c)
        _doc(a, "secret.txt", "Students reading program with confidential pricing.")
        assert _count_embeddings(a.user["org_id"]) == 1
        with org_session(b.user["org_id"]) as s:  # b's session cannot see a's vectors, even unfiltered
            assert s.execute(text("SELECT count(*) FROM chunk_embeddings")).scalar() == 0
        assert b.get("/library/search", params={"q": "pupil literacy"}).json() == []


def test_drafting_uses_hybrid_search(client, fake_llm, fake_embedder):
    _doc(client, "reading.txt", "Our tutoring program raised students' reading scores by two grade levels.")
    bid = client.post("/bids", json={"title": "Literacy services"}).json()
    client.post(f"/bids/{bid['id']}/files", data={"kind": "base"},
                files={"file": ("rfp.txt", b"[Page 1]\nThe bidder shall describe pupil literacy outcomes.\n",
                                "text/plain")})
    client.post(f"/bids/{bid['id']}/draft", json={})
    _context, sources = fake_llm.draft_calls[-1]
    assert "reading scores" in sources


# ---------------------------------------------------------------- units


def test_rank_fusion():
    def h(i):
        return Hit(Chunk(id=i, org_id=1, source_type="document", source_id=1, text="", label=str(i)), 0)

    fused = retrieval.fuse([[h(1), h(2), h(3)], [h(3), h(4), h(1)]], k=4, rrf_k=60)
    assert [x.chunk.id for x in fused] == [1, 3, 2, 4]  # both lists agree on 1 and 3


def test_openai_compatible_embedder_batches_and_classifies_errors(monkeypatch):
    seen = []

    def handler(request):
        body = __import__("json").loads(request.content)
        seen.append(len(body["input"]))
        data = [{"index": i, "embedding": [float(i)]} for i in reversed(range(len(body["input"])))]
        return httpx.Response(200, json={"data": data})

    e = embeddings.OpenAICompatibleEmbedder(
        model="nomic-embed-text", client=httpx.Client(base_url="http://x/v1", transport=httpx.MockTransport(handler)))
    out = e.embed_documents([f"t{i}" for i in range(70)])
    assert seen == [64, 6] and out[1] == [1.0] and len(out) == 70  # batched, and put back in order

    down = embeddings.OpenAICompatibleEmbedder(
        model="m", client=httpx.Client(base_url="http://x/v1",
                                       transport=httpx.MockTransport(lambda r: httpx.Response(503, text="busy"))))
    with pytest.raises(LLMError) as err:
        down.embed_query("q")
    assert jobs.is_temporary(err.value)


def test_a_running_job_does_not_block_new_work_for_the_same_target(client):
    org = client.user["org_id"]
    jobs.register("test_noop", lambda *a: None, lambda *a: None)
    with org_session(org) as s:
        jobs.enqueue(s, org, "test_noop", 7)
        s.commit()
    running = jobs.claim()
    with org_session(org) as s:
        jobs.enqueue(s, org, "test_noop", 7)  # new work arrives while the first job runs
        s.commit()
    jobs._finish(running, "queued", "temporary", delay=0)  # the first job wants a retry...
    with worker_session() as s:
        rows = s.scalars(select(Job).where(Job.kind == "test_noop", Job.target_id == 7).order_by(Job.id)).all()
        assert [j.status for j in rows] == ["done", "queued"]  # ...but the newer queued job covers it
    jobs.run_until_idle()
    del jobs.HANDLERS["test_noop"]
