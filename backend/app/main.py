import re
import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import auth, export, pipeline, retrieval
from .auth import current_org
from .config import settings
from .db import check_role, get_session
from .models import (
    Answer,
    Bid,
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

@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    check_role()
    yield


app = FastAPI(title="Automated RFP Response Engine", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(auth.router)

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


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
    name = Path(upload.filename or "upload").name
    if Path(name).suffix.lower() not in SUPPORTED:
        raise HTTPException(415, f"Unsupported file type. Use one of: {', '.join(sorted(SUPPORTED))}")
    data = await upload.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 50 MB.")
    if not data:
        raise HTTPException(400, "File is empty.")
    folder = settings.storage_dir / str(org)
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    path = folder / f"{uuid.uuid4().hex}_{safe}"
    path.write_bytes(data)
    return path


@app.get("/health")
def health():
    return {"ok": True, "model": settings.model}


# ------------------------------------------------------------------ library


@app.post("/library/documents", response_model=LibraryDocumentOut, status_code=201)
async def upload_library_document(
    s: DB, org: Org, bg: BackgroundTasks,
    file: UploadFile = File(...), doc_type: str = Form("other"),
):
    path = await _save_upload(file, org)
    doc = LibraryDocument(org_id=org, filename=Path(file.filename).name, doc_type=doc_type, storage_path=str(path))
    s.add(doc)
    s.commit()
    bg.add_task(pipeline.ingest_document, org, doc.id)
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
    Path(doc.storage_path).unlink(missing_ok=True)
    s.delete(doc)
    s.commit()


@app.get("/library/search", response_model=list[SearchHitOut])
def search_library(q: str, s: DB, org: Org, k: int = 10):
    return [
        SearchHitOut(
            chunk_id=h.chunk.id, source_type=h.chunk.source_type, source_id=h.chunk.source_id,
            label=h.chunk.label, page=h.chunk.page, heading=h.chunk.heading, text=h.chunk.text, score=h.score,
        )
        for h in retrieval.search(s, org, q, k)
    ]


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
    for f in b.files:
        Path(f.storage_path).unlink(missing_ok=True)
    s.delete(b)
    s.commit()


@app.post("/bids/{bid_id}/files", response_model=SolicitationFileOut, status_code=201)
async def upload_solicitation_file(
    bid_id: int, s: DB, org: Org, bg: BackgroundTasks,
    file: UploadFile = File(...), kind: str = Form("base"),
):
    if kind not in ("base", "addendum"):
        raise HTTPException(422, "kind must be 'base' or 'addendum'")
    bid = _owned(s, Bid, bid_id, org)
    path = await _save_upload(file, org)
    seq = len(bid.files) + 1
    f = SolicitationFile(org_id=org, bid_id=bid.id, filename=Path(file.filename).name, kind=kind,
                         sequence=seq, storage_path=str(path))
    s.add(f)
    s.commit()
    bg.add_task(pipeline.process_solicitation_file, org, f.id)
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
def draft_answers(bid_id: int, body: DraftRequest, s: DB, org: Org, bg: BackgroundTasks):
    _owned(s, Bid, bid_id, org)
    ids = pipeline.queue_answers(s, bid_id, body.requirement_ids, body.force)
    if ids:
        bg.add_task(pipeline.draft_bid, org, bid_id, ids)
    return DraftQueued(queued=ids)


@app.patch("/answers/{aid}", response_model=AnswerOut)
def update_answer(aid: int, body: AnswerPatch, s: DB, org: Org):
    a = _owned(s, Answer, aid, org)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
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


def _filename(bid: Bid, suffix: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", bid.title).strip("_")[:60] + suffix


@app.get("/bids/{bid_id}/export/response.docx")
def export_response(bid_id: int, s: DB, org: Org):
    b = _owned(s, Bid, bid_id, org)
    return Response(
        export.export_docx(b),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{_filename(b, "_response.docx")}"'},
    )


@app.get("/bids/{bid_id}/export/matrix.xlsx")
def export_matrix(bid_id: int, s: DB, org: Org):
    b = _owned(s, Bid, bid_id, org)
    return Response(
        export.export_matrix_xlsx(b),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{_filename(b, "_compliance_matrix.xlsx")}"'},
    )
