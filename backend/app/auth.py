"""Email + password sign-in with server-side sessions, organizations and invites.

- Passwords are hashed with Argon2id.
- The browser gets a random token in an httpOnly cookie; only its SHA-256 is stored,
  so a database leak does not leak usable sessions. Sessions can be revoked (logout).
- The first user of an organization is its admin; admins invite teammates by link.
"""

import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import settings
from .db import bind_org, get_session
from .models import AuthSession, Invite, Organization, User

router = APIRouter(prefix="/auth", tags=["auth"])
_hasher = PasswordHasher()
DB = Annotated[Session, Depends(get_session)]
INVITE_DAYS = 7


# ---------------------------------------------------------------- helpers


def hash_password(pw: str) -> str:
    return _hasher.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, pw)
    except (VerificationError, InvalidHashError):
        return False


# A fixed hash so unknown emails take as long to reject as wrong passwords.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _RateLimiter:
    """In-process limiter for failed logins (per email and per IP).

    Good enough for one API process; move to Redis when running several.
    """

    def __init__(self, limit: int = 10, window_s: int = 15 * 60):
        self.limit, self.window = limit, window_s
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def blocked(self, key: str) -> bool:
        q, cutoff = self.hits[key], time.monotonic() - self.window
        while q and q[0] < cutoff:
            q.popleft()
        return len(q) >= self.limit

    def fail(self, key: str) -> None:
        self.hits[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        self.hits.pop(key, None)


login_limiter = _RateLimiter()


def _start_session(s: Session, user: User, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    s.add(AuthSession(user_id=user.id, token_hash=_token_hash(token),
                      expires_at=_utcnow() + timedelta(days=settings.session_days)))
    s.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.expires_at < _utcnow()))
    s.commit()
    response.set_cookie(
        settings.cookie_name, token, max_age=settings.session_days * 86400, httponly=True,
        secure=settings.cookie_secure, samesite="lax", path="/",
    )


# ---------------------------------------------------------------- dependencies


def current_user(
    s: DB, token: Annotated[str | None, Cookie(alias=settings.cookie_name)] = None,
) -> User:
    if not token:
        raise HTTPException(401, "Not signed in")
    sess = s.scalar(select(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
    if sess is None or sess.expires_at < _utcnow() or not sess.user.is_active:
        raise HTTPException(401, "Session expired. Please sign in again.")
    return sess.user


CurrentUser = Annotated[User, Depends(current_user)]


def current_org(s: DB, user: CurrentUser) -> int:
    """The signed-in user's organization; also binds row-level security for this request."""
    bind_org(s, user.org_id)
    return user.org_id


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Only organization admins can do this.")
    return user


# ---------------------------------------------------------------- schemas


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    org_id: int
    org_name: str


def _user_out(u: User) -> UserOut:
    return UserOut(id=u.id, email=u.email, name=u.name, role=u.role, org_id=u.org_id, org_name=u.organization.name)


Password = Annotated[str, Field(min_length=10, max_length=200)]


class SignupIn(BaseModel):
    org_name: str = Field(min_length=2, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: Password


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class InviteIn(BaseModel):
    email: EmailStr
    role: Literal["admin", "member"] = "member"


class InviteOut(BaseModel):
    id: int
    email: str
    role: str
    expires_at: datetime
    accepted_at: datetime | None
    token: str | None = None  # only returned once, when the invite is created


class AcceptInviteIn(BaseModel):
    token: str
    name: str = Field(min_length=1, max_length=200)
    password: Password


class MemberOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool


class MemberPatch(BaseModel):
    role: Literal["admin", "member"] | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------- routes


@router.post("/signup", response_model=UserOut, status_code=201)
def signup(body: SignupIn, s: DB, response: Response):
    if not settings.allow_signup:
        raise HTTPException(403, "Sign-up is disabled. Ask an admin for an invite.")
    email = body.email.lower()
    if s.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    org = Organization(name=body.org_name.strip())
    s.add(org)
    s.flush()
    user = User(org_id=org.id, email=email, name=body.name.strip(), password_hash=hash_password(body.password), role="admin")
    s.add(user)
    s.flush()
    _start_session(s, user, response)
    return _user_out(user)


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, s: DB, request: Request, response: Response):
    email = body.email.lower()
    keys = [f"email:{email}", f"ip:{request.client.host if request.client else '?'}"]
    if any(login_limiter.blocked(k) for k in keys):
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    user = s.scalar(select(User).where(User.email == email))
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not (user and ok and user.is_active):
        for k in keys:
            login_limiter.fail(k)
        raise HTTPException(401, "Incorrect email or password.")
    for k in keys:
        login_limiter.reset(k)
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    _start_session(s, user, response)
    return _user_out(user)


@router.post("/logout", status_code=204)
def logout(s: DB, response: Response, token: Annotated[str | None, Cookie(alias=settings.cookie_name)] = None):
    if token:
        s.execute(delete(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
        s.commit()
    response.delete_cookie(settings.cookie_name, path="/")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return _user_out(user)


@router.get("/members", response_model=list[MemberOut])
def list_members(s: DB, user: CurrentUser):
    return [
        MemberOut(id=u.id, email=u.email, name=u.name, role=u.role, is_active=u.is_active)
        for u in s.scalars(select(User).where(User.org_id == user.org_id).order_by(User.name))
    ]


@router.patch("/members/{uid}", response_model=MemberOut)
def update_member(uid: int, body: MemberPatch, s: DB, admin: Annotated[User, Depends(require_admin)]):
    u = s.get(User, uid)
    if u is None or u.org_id != admin.org_id:
        raise HTTPException(404, "Member not found")
    if u.id == admin.id and (body.role == "member" or body.is_active is False):
        raise HTTPException(400, "You cannot demote or deactivate yourself.")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(u, k, v)
    if body.is_active is False:
        s.execute(delete(AuthSession).where(AuthSession.user_id == u.id))
    s.commit()
    return MemberOut(id=u.id, email=u.email, name=u.name, role=u.role, is_active=u.is_active)


@router.get("/invites", response_model=list[InviteOut])
def list_invites(s: DB, admin: Annotated[User, Depends(require_admin)]):
    rows = s.scalars(select(Invite).where(Invite.org_id == admin.org_id).order_by(Invite.created_at.desc()))
    return [InviteOut(id=i.id, email=i.email, role=i.role, expires_at=i.expires_at, accepted_at=i.accepted_at) for i in rows]


@router.post("/invites", response_model=InviteOut, status_code=201)
def create_invite(body: InviteIn, s: DB, admin: Annotated[User, Depends(require_admin)]):
    email = body.email.lower()
    if s.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "This person already has an account.")
    token = secrets.token_urlsafe(32)
    inv = Invite(org_id=admin.org_id, email=email, role=body.role, token_hash=_token_hash(token),
                 invited_by=admin.id, expires_at=_utcnow() + timedelta(days=INVITE_DAYS))
    s.add(inv)
    s.commit()
    # No email service yet: the admin copies the link and sends it themselves.
    return InviteOut(id=inv.id, email=inv.email, role=inv.role, expires_at=inv.expires_at, accepted_at=None, token=token)


@router.delete("/invites/{iid}", status_code=204)
def revoke_invite(iid: int, s: DB, admin: Annotated[User, Depends(require_admin)]):
    inv = s.get(Invite, iid)
    if inv is None or inv.org_id != admin.org_id:
        raise HTTPException(404, "Invite not found")
    s.delete(inv)
    s.commit()


@router.get("/invites/lookup")
def lookup_invite(token: str, s: DB):
    inv = _valid_invite(s, token)
    return {"email": inv.email, "org_name": s.get(Organization, inv.org_id).name}


@router.post("/accept-invite", response_model=UserOut, status_code=201)
def accept_invite(body: AcceptInviteIn, s: DB, response: Response):
    inv = _valid_invite(s, body.token)
    if s.scalar(select(User.id).where(User.email == inv.email)):
        raise HTTPException(409, "An account with this email already exists.")
    user = User(org_id=inv.org_id, email=inv.email, name=body.name.strip(),
                password_hash=hash_password(body.password), role=inv.role)
    s.add(user)
    inv.accepted_at = _utcnow()
    s.flush()
    _start_session(s, user, response)
    return _user_out(user)


def _valid_invite(s: Session, token: str) -> Invite:
    inv = s.scalar(select(Invite).where(Invite.token_hash == _token_hash(token)))
    if inv is None or inv.accepted_at is not None or inv.expires_at < _utcnow():
        raise HTTPException(404, "This invite link is invalid or has expired.")
    return inv
