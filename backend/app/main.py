import logging
import re
import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import auth, export, jobs, pipeline, retrieval
from .auth import current_org
from .config import settings
from .db import check_role, get_session
from .models import (
    Answer,
    Bid,
    Chunk,
    Credential,
    LibraryDocument,
    ProjectRecord,
    Requirement,
    SolicitationFile,
)
from .parsing import SUPPORTED
from .schemas import (
    AnswerOut,
    AnswerPatch,
    BidIn,
    BidListItem,
    BidOut,
    BidPatch,
    SavedAnswerOut,
    CredentialIn,
    CredentialOut,
    DraftQueued,
    DraftRequest,
    LibraryDocumentOut,
    ProjectIn,
    ProjectOut,
    RequirementIn,
    RequirementOut,
    RequirementPatch,
    SearchHitOut,
    SolicitationFileOut,
)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    check_role()
    # Simple deployments run the job worker inside the API process; larger ones set
    # RFP_EMBEDDED_WORKER=false and run `python -m app.worker` separately (as many as needed).
    worker = jobs.Worker().start() if settings.embedded_worker else None
    yield
    if worker:
        worker.stop(wait_s=5)  # unfinished jobs are taken over after a restart (heartbeat lease)


app = FastAPI(title="Automated RFP Response Engine", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(auth.router)

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """API responses hold customer data: never cache them, sniff them or show them in a frame."""
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Refuse oversized uploads before the body is read (a reverse proxy should cap it too)."""
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_UPLOAD_BYTES + 1024 * 1024:
        return JSONResponse({"detail": "File is larger than 50 MB."}, status_code=413)
    return await call_next(request)


@app.middleware("http")
async def block_cross_site_writes(request: Request, call_next):
    """CSRF defence on top of SameSite=Lax cookies: browsers send Origin on writes,
    and only our own frontend origins may change data."""
    origin = request.headers.get("origin")
    if request.method in UNSAFE and origin and origin not in settings.cors_origins:
        return JSONResponse({"detail": "Cross-site request blocked"}, status_code=403)
    return await call_next(request)


DB = Annotated[Session, Depends(get_session)]


Org = Annotated[int, Depends(current_org)]


def _owned(s: Session, model, obj_id: int, org: int):
    obj = s.get(model, obj_id)
    if obj is None or obj.org_id != org:
        raise HTTPException(404, f"{model.__name__} {obj_id} not found")
    return obj


async def _save_upload(upload: UploadFile, org: int) -> Path:
    """Stream the upload to storage in 1 MB pieces, so a large file is never held in memory."""
    name = Path(upload.filename or "upload").name
    if Path(name).suffix.lower() not in SUPPORTED:
        raise HTTPException(415, f"Unsupported file type. Use one of: {', '.join(sorted(SUPPORTED))}")
    folder = settings.storage_dir / str(org)
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w.-]", "_", name)
    path = folder / f"{uuid.uuid4().hex}_{safe}"
    size = 0
    try:
        with path.open("wb") as out:
            while piece := await upload.read(1024 * 1024):
                size += len(piece)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "File is larger than 50 MB.")
                out.write(piece)
        if size == 0:
            raise HTTPException(400, "File is empty.")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _remove_files(paths: list[str]) -> None:
    for p in paths:
        try:
            Path(p).unlink(missing_ok=True)
        except OSError:
            log.warning("Could not delete stored file %s", p)


@app.get("/health")
def health():
    provider = settings.llm_provider
    model = settings.model if provider == "claude" else settings.openai_model
    return {"ok": True, "llm_provider": provider, "model": model}


# ------------------------------------------------------------------ library


@app.post("/library/documents", response_model=LibraryDocumentOut, status_code=201)
async def upload_library_document(
    s: DB, org: Org,
    file: UploadFile = File(...), doc_type: str = Form("other"),
):
    path = await _save_upload(file, org)
    doc = LibraryDocument(org_id=org, filename=Path(file.filename).name, doc_type=doc_type, storage_path=str(path))
    s.add(doc)
    s.flush()
    jobs.enqueue(s, org, "ingest_document", doc.id)
    s.commit()  # the document and its job are saved together
    return doc


@app.get("/library/documents", response_model=list[LibraryDocumentOut])
def list_library_documents(s: DB, org: Org):
    return s.scalars(
        select(LibraryDocument).where(LibraryDocument.org_id == org).order_by(LibraryDocument.created_at.desc())
    ).all()


@app.delete("/library/documents/{doc_id}", status_code=204)
def delete_library_document(doc_id: int, s: DB, org: Org):
    doc = _owned(s, LibraryDocument, doc_id, org)
    retrieval.remove_source(s, org, "document", doc.id)
    s.delete(doc)
    s.commit()
    _remove_files([doc.storage_path])  # only after the database change has succeeded


@app.get("/library/search", response_model=list[SearchHitOut])
def search_library(q: str, s: DB, org: Org, k: int = 10):
    return [
        SearchHitOut(
            chunk_id=h.chunk.id, source_type=h.chunk.source_type, source_id=h.chunk.source_id,
            label=h.chunk.label, page=h.chunk.page, heading=h.chunk.heading, text=h.chunk.text, score=h.score,
        )
        for h in retrieval.search(s, org, q, k)
    ]


@app.get("/library/answers", response_model=list[SavedAnswerOut])
def list_saved_answers(s: DB, org: Org):
    """Approved answers saved to the library (they are cited in later drafts like any other source)."""
    rows = s.scalars(
        select(Chunk).where(Chunk.org_id == org, Chunk.source_type == "answer").order_by(Chunk.id.desc())
    ).all()
    live = set(s.scalars(select(Answer.id).where(Answer.org_id == org, Answer.id.in_([c.source_id for c in rows]))))
    out = []
    for c in rows:
        question, _, answer = c.text.removeprefix("Question: ").partition("\nApproved answer: ")
        out.append(SavedAnswerOut(chunk_id=c.id, label=c.label, question=question, answer=answer,
                                  bid_deleted=c.source_id not in live))
    return out


@app.delete("/library/answers/{chunk_id}", status_code=204)
def delete_saved_answer(chunk_id: int, s: DB, org: Org):
    """Remove a saved answer from the library. The answer in its bid (if any) is not changed."""
    c = s.get(Chunk, chunk_id)
    if c is None or c.org_id != org or c.source_type != "answer":
        raise HTTPException(404, f"Saved answer {chunk_id} not found")
    s.delete(c)
    s.commit()


# ------------------------------------------------------------------ projects & credentials


@app.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, s: DB, org: Org):
    p = ProjectRecord(org_id=org, **body.model_dump())
    s.add(p)
    s.flush()
    pipeline.index_project(s, p)
    s.commit()
    return p


@app.get("/projects", response_model=list[ProjectOut])
def list_projects(s: DB, org: Org):
    return s.scalars(select(ProjectRecord).where(ProjectRecord.org_id == org).order_by(ProjectRecord.name)).all()


@app.put("/projects/{pid}", response_model=ProjectOut)
def update_project(pid: int, body: ProjectIn, s: DB, org: Org):
    p = _owned(s, ProjectRecord, pid, org)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    pipeline.index_project(s, p)
    s.commit()
    return p


@app.delete("/projects/{pid}", status_code=204)
def delete_project(pid: int, s: DB, org: Org):
    p = _owned(s, ProjectRecord, pid, org)
    retrieval.remove_source(s, org, "project", p.id)
    s.delete(p)
    s.commit()


def _cred_out(c: Credential) -> CredentialOut:
    out = CredentialOut.model_validate(c)
    out.days_to_expiry = (c.expires_on - date.today()).days if c.expires_on else None
    return out


@app.post("/credentials", response_model=CredentialOut, status_code=201)
def create_credential(body: CredentialIn, s: DB, org: Org):
    c = Credential(org_id=org, **body.model_dump())
    s.add(c)
    s.flush()
    pipeline.index_credential(s, c)
    s.commit()
    return _cred_out(c)


@app.get("/credentials", response_model=list[CredentialOut])
def list_credentials(s: DB, org: Org):
    rows = s.scalars(select(Credential).where(Credential.org_id == org).order_by(Credential.expires_on)).all()
    return [_cred_out(c) for c in rows]


@app.get("/credentials/expiring", response_model=list[CredentialOut])
def expiring_credentials(s: DB, org: Org, days: int = 30):
    cutoff = date.today() + timedelta(days=days)
    rows = s.scalars(
        select(Credential).where(
            Credential.org_id == org, Credential.expires_on.is_not(None), Credential.expires_on <= cutoff
        ).order_by(Credential.expires_on)
    ).all()
    return [_cred_out(c) for c in rows]


@app.put("/credentials/{cid}", response_model=CredentialOut)
def update_credential(cid: int, body: CredentialIn, s: DB, org: Org):
    c = _owned(s, Credential, cid, org)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    pipeline.index_credential(s, c)
    s.commit()
    return _cred_out(c)


@app.delete("/credentials/{cid}", status_code=204)
def delete_credential(cid: int, s: DB, org: Org):
    c = _owned(s, Credential, cid, org)
    retrieval.remove_source(s, org, "credential", c.id)
    s.delete(c)
    s.commit()


# ------------------------------------------------------------------ bids


@app.post("/bids", response_model=BidOut, status_code=201)
def create_bid(body: BidIn, s: DB, org: Org):
    b = Bid(org_id=org, **body.model_dump())
    s.add(b)
    s.commit()
    return b


@app.get("/bids", response_model=list[BidListItem])
def list_bids(s: DB, org: Org):
    bids = s.scalars(select(Bid).where(Bid.org_id == org).order_by(Bid.due_date.is_(None), Bid.due_date)).all()
    counts = dict(s.execute(
        select(Requirement.bid_id, func.count()).where(Requirement.org_id == org, Requirement.status != "removed")
        .group_by(Requirement.bid_id)
    ).all())
    answered = dict(s.execute(
        select(Requirement.bid_id, func.count()).join(Answer)
        .where(Requirement.org_id == org, Answer.status.in_(["accepted", "approved"]))
        .group_by(Requirement.bid_id)
    ).all())
    out = []
    for b in bids:
        item = BidListItem.model_validate(b)
        item.requirement_count, item.answered_count = counts.get(b.id, 0), answered.get(b.id, 0)
        out.append(item)
    return out


@app.get("/bids/{bid_id}", response_model=BidOut)
def get_bid(bid_id: int, s: DB, org: Org):
    return _owned(s, Bid, bid_id, org)


@app.patch("/bids/{bid_id}", response_model=BidOut)
def update_bid(bid_id: int, body: BidPatch, s: DB, org: Org):
    b = _owned(s, Bid, bid_id, org)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(b, k, v)
    s.commit()
    return b


@app.delete("/bids/{bid_id}", status_code=204)
def delete_bid(bid_id: int, s: DB, org: Org):
    b = _owned(s, Bid, bid_id, org)
    paths = [f.storage_path for f in b.files]
    s.delete(b)
    s.commit()
    _remove_files(paths)


@app.post("/bids/{bid_id}/files", response_model=SolicitationFileOut, status_code=201)
async def upload_solicitation_file(
    bid_id: int, s: DB, org: Org,
    file: UploadFile = File(...), kind: str = Form("base"),
):
    if kind not in ("base", "addendum"):
        raise HTTPException(422, "kind must be 'base' or 'addendum'")
    _owned(s, Bid, bid_id, org)
    path = await _save_upload(file, org)
    # Lock the bid row so two uploads at once cannot get the same sequence number.
    bid = s.get(Bid, bid_id, with_for_update=True)
    seq = (s.scalar(select(func.max(SolicitationFile.sequence)).where(SolicitationFile.bid_id == bid.id)) or 0) + 1
    f = SolicitationFile(org_id=org, bid_id=bid.id, filename=Path(file.filename).name, kind=kind,
                         sequence=seq, storage_path=str(path))
    s.add(f)
    s.flush()
    jobs.enqueue(s, org, "process_file", f.id)
    s.commit()
    return f


@app.get("/bids/{bid_id}/requirements", response_model=list[RequirementOut])
def list_requirements(bid_id: int, s: DB, org: Org, include_removed: bool = False):
    b = _owned(s, Bid, bid_id, org)
    return [r for r in b.requirements if include_removed or r.status != "removed"]


@app.post("/bids/{bid_id}/requirements", response_model=RequirementOut, status_code=201)
def add_requirement(bid_id: int, body: RequirementIn, s: DB, org: Org):
    """Manual add, for anything the extraction missed."""
    b = _owned(s, Bid, bid_id, org)
    seq = max((r.sequence for r in b.requirements), default=0) + 1
    r = Requirement(org_id=org, bid_id=b.id, sequence=seq, **body.model_dump())
    s.add(r)
    s.commit()
    return r


@app.patch("/requirements/{rid}", response_model=RequirementOut)
def update_requirement(rid: int, body: RequirementPatch, s: DB, org: Org):
    r = _owned(s, Requirement, rid, org)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    s.commit()
    return r


@app.post("/bids/{bid_id}/draft", response_model=DraftQueued, status_code=202)
def draft_answers(bid_id: int, body: DraftRequest, s: DB, org: Org):
    _owned(s, Bid, bid_id, org)
    return DraftQueued(queued=pipeline.queue_answers(s, bid_id, body.requirement_ids, body.force))


@app.patch("/answers/{aid}", response_model=AnswerOut)
def update_answer(aid: int, body: AnswerPatch, s: DB, org: Org):
    a = _owned(s, Answer, aid, org)
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(a, k, v)
    if "final_text" in changes:
        pipeline.recheck_facts(s, a)  # a person's edits are checked against the sources too
    s.commit()
    return a


@app.post("/answers/{aid}/approve", response_model=AnswerOut)
def approve_answer(aid: int, s: DB, org: Org):
    """Approve the answer and save it to the library for reuse in future bids."""
    a = _owned(s, Answer, aid, org)
    if not (a.final_text or a.draft_text):
        raise HTTPException(400, "Nothing to approve: the answer is empty.")
    a.final_text = a.final_text or a.draft_text
    a.status = "approved"
    a.requirement.status = "met"
    pipeline.index_approved_answer(s, a)
    s.commit()
    return a


@app.get("/bids/{bid_id}/readiness")
def bid_readiness(bid_id: int, s: DB, org: Org):
    return export.readiness(_owned(s, Bid, bid_id, org))


def _attachment(bid: Bid, suffix: str) -> str:
    """Content-Disposition with the bid title kept in any script (RFC 6266 filename*), plus a plain
    ASCII fallback for old clients. A title like "भवन निर्माण" no longer becomes "_response.docx"."""
    title = re.sub(r'[\x00-\x1f\x7f"\\/:*?<>|]+', "_", bid.title).strip(" ._")[:80] or f"bid_{bid.id}"
    ascii_name = re.sub(r"[^A-Za-z0-9]+", "_", bid.title).strip("_")[:60] or f"bid_{bid.id}"
    return f"attachment; filename=\"{ascii_name}{suffix}\"; filename*=UTF-8''{quote(title + suffix, safe='')}"


@app.get("/bids/{bid_id}/export/response.docx")
def export_response(bid_id: int, s: DB, org: Org):
    b = _owned(s, Bid, bid_id, org)
    return Response(
        export.export_docx(b),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": _attachment(b, "_response.docx")},
    )


@app.get("/bids/{bid_id}/export/matrix.xlsx")
def export_matrix(bid_id: int, s: DB, org: Org):
    b = _owned(s, Bid, bid_id, org)
    return Response(
        export.export_matrix_xlsx(b),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": _attachment(b, "_compliance_matrix.xlsx")},
    )
