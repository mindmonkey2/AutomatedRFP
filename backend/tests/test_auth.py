"""Sign-in, sessions, invites, CSRF, and tenant isolation (app-level and Postgres RLS)."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal, bind_org
from app.main import app
from app.models import Bid, Chunk, ProjectRecord

from .conftest import PASSWORD, signup


def test_requires_sign_in(anon):
    assert anon.get("/bids").status_code == 401
    assert anon.get("/health").status_code == 200


def test_signup_login_logout(anon):
    me = signup(anon, "Ridge Construction")
    assert me["role"] == "admin" and me["org_name"] == "Ridge Construction"
    assert anon.get("/auth/me").json()["email"] == me["email"]

    assert anon.post("/auth/logout").status_code == 204
    assert anon.get("/auth/me").status_code == 401

    bad = anon.post("/auth/login", json={"email": me["email"], "password": "wrong-password!"})
    assert bad.status_code == 401
    ok = anon.post("/auth/login", json={"email": me["email"].upper(), "password": PASSWORD})
    assert ok.status_code == 200 and anon.get("/bids").status_code == 200


def test_duplicate_email_and_weak_password(anon):
    me = signup(anon)
    r = anon.post("/auth/signup", json={"org_name": "X Co", "name": "X", "email": me["email"], "password": PASSWORD})
    assert r.status_code == 409
    r = anon.post("/auth/signup", json={"org_name": "X Co", "name": "X", "email": "a@b.com", "password": "short"})
    assert r.status_code == 422


def test_login_rate_limit(anon):
    me = signup(anon)
    anon.post("/auth/logout")
    for _ in range(10):
        anon.post("/auth/login", json={"email": me["email"], "password": "wrong-password!"})
    r = anon.post("/auth/login", json={"email": me["email"], "password": PASSWORD})
    assert r.status_code == 429


def test_invite_flow(client, fake_llm):
    inv = client.post("/auth/invites", json={"email": "Estimator@Example.com"}).json()
    assert inv["token"] and inv["email"] == "estimator@example.com"
    # Token is shown once; the listing does not expose it.
    assert client.get("/auth/invites").json()[0]["token"] is None

    with TestClient(app) as teammate:
        info = teammate.get("/auth/invites/lookup", params={"token": inv["token"]}).json()
        assert info["org_name"] == "Acme Builders"
        r = teammate.post("/auth/accept-invite", json={"token": inv["token"], "name": "Sam", "password": PASSWORD})
        assert r.status_code == 201 and r.json()["role"] == "member"
        assert r.json()["org_id"] == client.user["org_id"]
        # Members cannot invite; the invite cannot be reused.
        assert teammate.post("/auth/invites", json={"email": "x@example.com"}).status_code == 403
        r = teammate.post("/auth/accept-invite", json={"token": inv["token"], "name": "Sam", "password": PASSWORD})
        assert r.status_code == 404

    members = client.get("/auth/members").json()
    assert {m["role"] for m in members} == {"admin", "member"}
    sam = next(m for m in members if m["role"] == "member")
    assert client.patch(f"/auth/members/{sam['id']}", json={"is_active": False}).json()["is_active"] is False


def test_cross_site_write_blocked(client):
    r = client.post("/bids", json={"title": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post("/bids", json={"title": "x"}, headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 201


def test_tenant_isolation_api(fake_llm):
    with TestClient(app) as a, TestClient(app) as b:
        signup(a, "Org A")
        signup(b, "Org B")
        a.post("/projects", json={"name": "Secret Hospital Wing", "scope": "hospital expansion"})
        bid = a.post("/bids", json={"title": "A only"}).json()
        assert b.get("/library/search", params={"q": "hospital"}).json() == []
        assert b.get("/projects").json() == []
        assert b.get(f"/bids/{bid['id']}").status_code == 404
        assert b.patch(f"/bids/{bid['id']}", json={"title": "hijack"}).status_code == 404


def test_row_level_security_in_database(fake_llm):
    """Even a query with NO org filter only sees the bound organization's rows."""
    with TestClient(app) as a, TestClient(app) as b:
        org_a = signup(a, "RLS A")["org_id"]
        org_b = signup(b, "RLS B")["org_id"]
        a.post("/projects", json={"name": "A project", "scope": "bridge"})
        b.post("/projects", json={"name": "B project", "scope": "bridge"})

    with SessionLocal() as s:  # nothing bound: fail closed
        assert s.scalar(select(func.count()).select_from(ProjectRecord)) == 0
        assert s.scalar(select(func.count()).select_from(Chunk)) == 0
    with SessionLocal() as s:
        bind_org(s, org_a)
        names = s.scalars(select(ProjectRecord.name)).all()
        assert names == ["A project"]
        # Writing a row for another org is rejected by the policy's WITH CHECK.
        s.add(Bid(org_id=org_b, title="sneaky"))
        try:
            s.commit()
            raise AssertionError("RLS should have blocked this insert")
        except Exception as e:  # noqa: BLE001
            assert "row-level security" in str(e)
