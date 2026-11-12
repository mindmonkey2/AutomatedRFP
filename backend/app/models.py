"""ORM models.

Every tenant-owned table carries org_id; the app filters on it and Postgres row-level
security enforces it (see migrations/versions). organizations, users, auth_sessions and
invites are auth tables, read before the tenant is known, so they have no RLS policy.
"""

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Computed, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)  # stored lower-case
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default="member")  # admin|member
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    organization: Mapped[Organization] = relationship()


class AuthSession(Base):
    """Server-side login session. Only a SHA-256 of the cookie token is stored."""

    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    user: Mapped[User] = relationship()


class Invite(Base):
    __tablename__ = "invites"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(20), default="member")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LibraryDocument(Base):
    __tablename__ = "library_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    filename: Mapped[str] = mapped_column(String(500))
    doc_type: Mapped[str] = mapped_column(String(50), default="other")  # proposal|policy|resume|project_sheet|questionnaire|other
    storage_path: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|processing|ready|failed
    error: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    empty_pages: Mapped[list] = mapped_column(JSON, default=list)  # pages with no text layer (need OCR)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Chunk(Base):
    """A retrievable passage. source_type says where it came from."""

    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(20))  # document|project|credential|answer
    source_id: Mapped[int] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(String(500))
    label: Mapped[str] = mapped_column(String(500))  # human-readable source name for citations
    tsv = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(label, '') || ' ' || coalesce(heading, '') || ' ' || text)",
            persisted=True,
        ),
    )

    __table_args__ = (Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),)


class ProjectRecord(Base):
    __tablename__ = "project_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(300))
    client: Mapped[str | None] = mapped_column(String(300))
    sector: Mapped[str | None] = mapped_column(String(100))  # e.g. public-k12, federal, healthcare
    contract_value: Mapped[float | None] = mapped_column(Float)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    scope: Mapped[str | None] = mapped_column(Text)
    reference_name: Mapped[str | None] = mapped_column(String(200))
    reference_contact: Mapped[str | None] = mapped_column(String(300))


class Credential(Base):
    __tablename__ = "credentials"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50))  # license|bond|insurance|certification|other
    name: Mapped[str] = mapped_column(String(300))
    number: Mapped[str | None] = mapped_column(String(100))
    issuer: Mapped[str | None] = mapped_column(String(300))
    expires_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)


class Bid(Base):
    __tablename__ = "bids"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    agency: Mapped[str | None] = mapped_column(String(300))
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="open")
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    files: Mapped[list["SolicitationFile"]] = relationship(
        back_populates="bid", cascade="all, delete-orphan", order_by="SolicitationFile.sequence"
    )
    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="bid", cascade="all, delete-orphan", order_by="Requirement.sequence"
    )


class Job(Base):
    """A unit of background work (see app/jobs.py). Holds only ids and status, never document text."""

    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # ingest_document | process_file | draft_answer
    target_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|done|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    locked_by: Mapped[str | None] = mapped_column(String(100))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_jobs_claim", "status", "run_after"),
        # At most one live job per target, so a double click cannot draft the same answer twice.
        Index("uq_jobs_live_target", "kind", "target_id", unique=True,
              postgresql_where=text("status IN ('queued', 'running')")),
    )


class SolicitationFile(Base):
    __tablename__ = "solicitation_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    bid_id: Mapped[int] = mapped_column(ForeignKey("bids.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(500))
    kind: Mapped[str] = mapped_column(String(20))  # base|addendum
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    storage_path: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    error: Mapped[str | None] = mapped_column(Text)
    change_summary: Mapped[str | None] = mapped_column(Text)  # addenda: what changed
    progress: Mapped[str | None] = mapped_column(String(200))  # e.g. "Reading part 2 of 5"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    bid: Mapped[Bid] = relationship(back_populates="files")


class Requirement(Base):
    __tablename__ = "requirements"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    bid_id: Mapped[int] = mapped_column(ForeignKey("bids.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(30))  # see llm.REQUIREMENT_KINDS
    section: Mapped[str | None] = mapped_column(String(300))
    page: Mapped[int | None] = mapped_column(Integer)
    source_quote: Mapped[str | None] = mapped_column(Text)
    mandatory: Mapped[bool] = mapped_column(default=True)
    needs_response: Mapped[bool] = mapped_column(default=False)
    page_limit: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|drafted|met|na|removed
    changed_by_file_id: Mapped[int | None] = mapped_column(ForeignKey("solicitation_files.id", ondelete="SET NULL"))
    change_type: Mapped[str | None] = mapped_column(String(20))  # added|modified|removed

    bid: Mapped[Bid] = relationship(back_populates="requirements")
    answer: Mapped["Answer | None"] = relationship(
        back_populates="requirement", cascade="all, delete-orphan", uselist=False
    )


class Answer(Base):
    __tablename__ = "answers"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), unique=True, index=True
    )
    draft_text: Mapped[str | None] = mapped_column(Text)
    final_text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    confidence_reasons: Mapped[list] = mapped_column(JSON, default=list)
    unsupported_claims: Mapped[list] = mapped_column(JSON, default=list)
    # Figures and names in the text that the sources do not contain (app/factcheck.py)
    fact_issues: Mapped[list] = mapped_column(JSON, default=list)
    # queued|drafting|drafted|needs_review|accepted|approved|stale|failed
    status: Mapped[str] = mapped_column(String(20), default="queued")
    error: Mapped[str | None] = mapped_column(Text)
    assignee: Mapped[str | None] = mapped_column(String(200))
    due_date: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    requirement: Mapped[Requirement] = relationship(back_populates="answer")
    citations: Mapped[list["Citation"]] = relationship(
        back_populates="answer", cascade="all, delete-orphan", order_by="Citation.marker"
    )


class Citation(Base):
    __tablename__ = "citations"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    answer_id: Mapped[int] = mapped_column(ForeignKey("answers.id", ondelete="CASCADE"), index=True)
    marker: Mapped[int] = mapped_column(Integer)
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("chunks.id", ondelete="SET NULL"))
    quote: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(default=False)
    label: Mapped[str] = mapped_column(String(500))
    page: Mapped[int | None] = mapped_column(Integer)

    answer: Mapped[Answer] = relationship(back_populates="citations")
