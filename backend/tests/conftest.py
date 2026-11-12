"""Tests run against a real Postgres database (row-level security, full-text search).

Set TEST_DATABASE_URL to an empty database owned by a NON-superuser role, e.g.
    createuser rfp --pwprompt && createdb -O rfp rfp_test
The schema is dropped and rebuilt with the Alembic migrations at the start of the run.
"""

import os
import re
import tempfile
import uuid

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://rfp:rfp@localhost:5432/rfp_test")
os.environ["RFP_DATABASE_URL"] = TEST_DB
os.environ["RFP_STORAGE_DIR"] = tempfile.mkdtemp(prefix="rfp-test-files-")
os.environ["RFP_EMBEDDED_WORKER"] = "false"  # tests run queued jobs themselves (see _run_jobs_after)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app import jobs  # noqa: E402
from app import llm as llm_mod  # noqa: E402
from app.auth import login_limiter  # noqa: E402
from app.config import BACKEND_DIR  # noqa: E402
from app.llm import (  # noqa: E402
    AddendumChange,
    AddendumResult,
    DraftCitation,
    DraftResult,
    ExtractedRequirement,
    ExtractionResult,
)
from app.main import app  # noqa: E402


class FakeLLM:
    """Deterministic stand-in for Claude: one requirement per 'shall' sentence."""

    def __init__(self):
        self.draft_calls = []

    def extract_requirements(self, text):
        reqs, page = [], None
        for line in text.splitlines():
            m = re.fullmatch(r"\[Page (\d+)\]", line.strip())
            if m:
                page = int(m.group(1))
                continue
            if " shall " in line:
                describe = "describe" in line.lower()
                reqs.append(ExtractedRequirement(
                    text=line.strip(), kind="question" if describe else "submission", section="Section 3",
                    page=page, source_quote=line.strip(), mandatory=True, needs_response=describe, page_limit=None,
                ))
        return ExtractionResult(summary="Construction of a new elementary school.", requirements=reqs)

    def fill_gaps(self, sentences):
        return ExtractionResult(summary="", requirements=[])

    def draft_answer(self, context, sources):
        self.draft_calls.append((context, sources))
        m = re.search(r'<source number="1"[^>]*>\n(.+?)\n</source>', sources, re.S)
        if not m:
            return DraftResult(answer="[[TBD: experience]]", citations=[], unsupported_claims=["experience"], confidence=0.1)
        quote = m.group(1)[:60]
        return DraftResult(
            answer="We have completed similar K-12 projects [1].",
            citations=[DraftCitation(marker=1, source_number=1, quote=quote)],
            unsupported_claims=[], confidence=0.9,
        )

    def diff_addendum(self, requirements, addendum_text):
        first_id = int(re.search(r"id=(\d+)", requirements).group(1))
        return AddendumResult(
            summary="Due date moved; bonding requirement added.",
            changes=[
                AddendumChange(change_type="modified", requirement_id=first_id, explanation="Changed",
                               requirement=ExtractedRequirement(
                                   text="The bidder shall describe its K-12 experience in 5 pages.",
                                   kind="question", section="Section 3", page=2,
                                   source_quote="describe its K-12 experience", mandatory=True,
                                   needs_response=True, page_limit=None)),
                AddendumChange(change_type="added", requirement_id=None, explanation="New",
                               requirement=ExtractedRequirement(
                                   text="The bidder shall provide a 10% bid bond.", kind="form", section=None,
                                   page=1, source_quote="10% bid bond", mandatory=True, needs_response=False,
                                   page_limit=None)),
            ],
        )


@pytest.fixture(scope="session", autouse=True)
def _db():
    eng = create_engine(TEST_DB)
    with eng.begin() as conn:
        role = conn.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
        assert not (role.rolsuper or role.rolbypassrls), "TEST_DATABASE_URL must use a non-superuser role"
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    eng.dispose()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", TEST_DB)
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def _reset_limiter():
    login_limiter.hits.clear()


@pytest.fixture
def fake_llm():
    fake = FakeLLM()
    llm_mod.set_llm(fake)
    yield fake
    llm_mod.set_llm(None)


PASSWORD = "correct-horse-battery"


def signup(c: TestClient, org: str = "Acme Builders") -> dict:
    email = f"{uuid.uuid4().hex[:10]}@example.com"
    r = c.post("/auth/signup", json={"org_name": org, "name": "Pat Admin", "email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return r.json()


def _run_jobs_after(c: TestClient) -> TestClient:
    """After every request, run the jobs it queued, as a worker would, so a test can upload a file
    and read the result on the next line. Set `c.run_jobs = False` to leave jobs queued."""
    c.run_jobs = True

    def hook(_response):
        if c.run_jobs:
            jobs.run_until_idle()

    c.event_hooks = {"request": [], "response": [hook]}
    return c


@pytest.fixture
def anon(fake_llm):
    with TestClient(app) as c:
        yield _run_jobs_after(c)


@pytest.fixture
def client(fake_llm):
    """A client signed in as the admin of a fresh organization."""
    with TestClient(app) as c:
        _run_jobs_after(c)
        c.user = signup(c)
        yield c
