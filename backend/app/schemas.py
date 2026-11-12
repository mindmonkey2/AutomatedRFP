from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LibraryDocumentOut(ORM):
    id: int
    filename: str
    doc_type: str
    status: str
    error: str | None
    page_count: int | None
    chunk_count: int
    empty_pages: list[int]
    created_at: datetime


class SearchHitOut(BaseModel):
    chunk_id: int
    source_type: str
    source_id: int
    label: str
    page: int | None
    heading: str | None
    text: str
    score: float


class ProjectIn(BaseModel):
    name: str
    client: str | None = None
    sector: str | None = None
    contract_value: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    scope: str | None = None
    reference_name: str | None = None
    reference_contact: str | None = None


class ProjectOut(ProjectIn, ORM):
    id: int


CredentialKind = Literal["license", "bond", "insurance", "certification", "other"]


class CredentialIn(BaseModel):
    kind: CredentialKind
    name: str
    number: str | None = None
    issuer: str | None = None
    expires_on: date | None = None
    notes: str | None = None


class CredentialOut(CredentialIn, ORM):
    id: int
    days_to_expiry: int | None = None


class BidIn(BaseModel):
    title: str
    agency: str | None = None
    due_date: date | None = None


class BidPatch(BaseModel):
    title: str | None = None
    agency: str | None = None
    due_date: date | None = None
    status: Literal["open", "submitted", "won", "lost", "no_bid"] | None = None


class SolicitationFileOut(ORM):
    id: int
    filename: str
    kind: str
    sequence: int
    status: str
    error: str | None
    change_summary: str | None
    created_at: datetime


class BidOut(ORM):
    id: int
    title: str
    agency: str | None
    due_date: date | None
    status: str
    summary: str | None
    created_at: datetime
    files: list[SolicitationFileOut]


class BidListItem(ORM):
    id: int
    title: str
    agency: str | None
    due_date: date | None
    status: str
    requirement_count: int = 0
    answered_count: int = 0


class CitationOut(ORM):
    marker: int
    chunk_id: int | None
    quote: str
    verified: bool
    label: str
    page: int | None


class AnswerOut(ORM):
    id: int
    draft_text: str | None
    final_text: str | None
    confidence: float | None
    confidence_reasons: list[str]
    unsupported_claims: list[str]
    status: str
    error: str | None
    assignee: str | None
    due_date: date | None
    citations: list[CitationOut]


class RequirementOut(ORM):
    id: int
    sequence: int
    text: str
    kind: str
    section: str | None
    page: int | None
    source_quote: str | None
    mandatory: bool
    needs_response: bool
    page_limit: int | None
    status: str
    change_type: str | None
    changed_by_file_id: int | None
    answer: AnswerOut | None


class RequirementPatch(BaseModel):
    text: str | None = None
    status: Literal["open", "drafted", "met", "na", "removed"] | None = None
    needs_response: bool | None = None
    mandatory: bool | None = None


class RequirementIn(BaseModel):
    text: str
    kind: Literal["submission", "form", "page_limit", "format", "deadline", "evaluation", "qualification", "question"]
    section: str | None = None
    page: int | None = None
    mandatory: bool = True
    needs_response: bool = False
    page_limit: int | None = None


class AnswerPatch(BaseModel):
    final_text: str | None = None
    status: Literal["drafted", "needs_review", "accepted"] | None = None
    assignee: str | None = None
    due_date: date | None = None


class DraftRequest(BaseModel):
    requirement_ids: list[int] | None = None
    force: bool = False


class DraftQueued(BaseModel):
    queued: list[int]
