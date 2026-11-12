"""Background jobs: ingest library files, build the compliance matrix, diff addenda, draft answers.

The API enqueues these as durable jobs (app/jobs.py) and a worker runs them. Each handler opens
its own session bound to the job's organization, and records the outcome on the customer's row:
"retrying" (temporary failure, the queue will run it again), "failed" (needs a person) or done.
"""

import logging
import re
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import db, jobs
from .config import settings
from .llm import ExtractedRequirement, attr, get_llm, neutralize
from .models import (
    Answer,
    Bid,
    Chunk,
    Citation,
    Credential,
    LibraryDocument,
    ProjectRecord,
    Requirement,
    SolicitationFile,
)
from .parsing import chunk_pages, obligation_sentences, parse_file, windows, words
from .retrieval import add_chunk, remove_source, search

log = logging.getLogger(__name__)

REVIEWED = {"accepted", "approved"}


# ---------------------------------------------------------------- library


def _retry_note(job: "jobs.JobRun", e: Exception) -> str:
    return (f"Attempt {job.attempt} of {job.max_attempts} hit a temporary problem ({str(e)[:300]}). "
            f"Trying again in about {job.retry_delay():.0f} s.")


def ingest_document(org_id: int, doc_id: int, job: "jobs.JobRun | None" = None) -> None:
    with db.org_session(org_id) as s:
        doc = s.get(LibraryDocument, doc_id)
        if doc is None:
            return
        doc.status = "processing"
        s.commit()
        try:
            parsed = parse_file(Path(doc.storage_path))
            remove_source(s, doc.org_id, "document", doc.id)
            n = 0
            for c in chunk_pages(parsed.pages, settings.chunk_chars):
                add_chunk(
                    s,
                    Chunk(
                        org_id=doc.org_id, source_type="document", source_id=doc.id,
                        text=c.text, page=c.page, heading=c.heading, label=doc.filename,
                    ),
                )
                n += 1
            doc.page_count = parsed.page_count
            doc.empty_pages = parsed.empty_pages
            doc.chunk_count = n
            doc.status = "ready" if n else "failed"
            doc.error = None if n else "No text found. Scanned PDFs need OCR, which is not supported yet."
            s.commit()
        except Exception as e:
            s.rollback()
            doc = s.get(LibraryDocument, doc_id)
            if job and job.will_retry(e):
                doc.status, doc.error = "queued", _retry_note(job, e)
            else:
                doc.status, doc.error = "failed", str(e)[:2000]
            s.commit()
            raise


def _abandon_document(org_id: int, doc_id: int, message: str) -> None:
    with db.org_session(org_id) as s:
        if doc := s.get(LibraryDocument, doc_id):
            doc.status, doc.error = "failed", message
            s.commit()


def index_project(s: Session, p: ProjectRecord) -> None:
    remove_source(s, p.org_id, "project", p.id)
    parts = [
        f"Project: {p.name}",
        p.client and f"Client/owner: {p.client}",
        p.sector and f"Sector: {p.sector}",
        p.contract_value is not None and f"Contract value: ${p.contract_value:,.0f}",
        (p.start_date or p.end_date) and f"Dates: {p.start_date or '?'} to {p.end_date or 'ongoing'}",
        p.scope and f"Scope: {p.scope}",
        p.reference_name and f"Reference: {p.reference_name} {p.reference_contact or ''}".strip(),
    ]
    add_chunk(s, Chunk(org_id=p.org_id, source_type="project", source_id=p.id,
                       text="\n".join(x for x in parts if x), label=f"Project record: {p.name}"))


def index_credential(s: Session, c: Credential) -> None:
    remove_source(s, c.org_id, "credential", c.id)
    parts = [
        f"{c.kind.title()}: {c.name}",
        c.number and f"Number: {c.number}",
        c.issuer and f"Issued by: {c.issuer}",
        c.expires_on and f"Expires: {c.expires_on.isoformat()}",
        c.notes,
    ]
    add_chunk(s, Chunk(org_id=c.org_id, source_type="credential", source_id=c.id,
                       text="\n".join(x for x in parts if x), label=f"{c.kind.title()}: {c.name}"))


def index_approved_answer(s: Session, a: Answer) -> None:
    req = a.requirement
    remove_source(s, a.org_id, "answer", a.id)
    body = strip_markers(a.final_text or a.draft_text or "")
    add_chunk(s, Chunk(org_id=a.org_id, source_type="answer", source_id=a.id,
                       text=f"Question: {req.text}\nApproved answer: {body}",
                       label=f"Approved answer ({req.bid.title})"))


# ---------------------------------------------------------------- solicitations


PENDING = ("queued", "processing")


def process_solicitation_file(org_id: int, file_id: int, job: "jobs.JobRun | None" = None) -> None:
    """Read one uploaded solicitation file: extract the compliance matrix, or apply an addendum.

    Files of a bid are processed strictly in upload order: an addendum is compared against the
    requirements of the files before it, so while an earlier file is still pending this job is
    deferred (jobs.Defer) and runs again a few seconds later.
    """
    with db.org_session(org_id) as s:
        f = s.get(SolicitationFile, file_id)
        if f is None or f.status not in PENDING:
            return  # deleted, or already done
        # The bid row lock makes "is anything earlier still pending?" atomic against other files.
        s.get(Bid, f.bid_id, with_for_update=True)
        earlier_pending = s.scalar(
            select(func.count()).select_from(SolicitationFile).where(
                SolicitationFile.bid_id == f.bid_id, SolicitationFile.sequence < f.sequence,
                SolicitationFile.status.in_(PENDING),
            )
        )
        if earlier_pending:
            f.progress = "Waiting for the files uploaded before it."
            s.commit()
            raise jobs.Defer(5)
        f.status, f.progress, f.error = "processing", "Reading the document", None
        s.commit()
        try:
            parsed = parse_file(Path(f.storage_path))
            text = parsed.tagged_text()
            if not text.strip():
                raise ValueError("No text found in this file. Scanned PDFs need OCR, which is not supported yet.")
            if f.kind == "addendum" and _has_requirements(s, f.bid_id):
                _set_progress(org_id, file_id, "Comparing the addendum with the current requirements")
                _apply_addendum(s, f, text)
            else:
                _extract_base(s, f, text, lambda msg: _set_progress(org_id, file_id, msg))
            f.status, f.error, f.progress = "ready", None, None
            s.commit()
        except Exception as e:
            s.rollback()
            f = s.get(SolicitationFile, file_id)
            if job and job.will_retry(e):
                f.status, f.progress = "queued", _retry_note(job, e)
            else:
                f.status, f.error, f.progress = "failed", str(e)[:2000], None
            s.commit()
            raise


def _set_progress(org_id: int, file_id: int, message: str) -> None:
    """Record progress in its own short transaction, so the page shows it while the job runs."""
    with db.org_session(org_id) as s:
        if f := s.get(SolicitationFile, file_id):
            f.progress = message[:200]
            s.commit()


def _abandon_file(org_id: int, file_id: int, message: str) -> None:
    with db.org_session(org_id) as s:
        if f := s.get(SolicitationFile, file_id):
            f.status, f.error, f.progress = "failed", message, None
            s.commit()


def _has_requirements(s: Session, bid_id: int) -> bool:
    return bool(s.scalar(select(func.count()).select_from(Requirement).where(Requirement.bid_id == bid_id)))


def _next_sequence(s: Session, bid_id: int) -> int:
    return (s.scalar(select(func.max(Requirement.sequence)).where(Requirement.bid_id == bid_id)) or 0) + 1


def _add_requirement(s: Session, f: SolicitationFile, r: ExtractedRequirement, seq: int, change_type=None) -> Requirement:
    req = Requirement(
        org_id=f.org_id, bid_id=f.bid_id, sequence=seq, text=r.text.strip(), kind=r.kind,
        section=r.section, page=r.page, source_quote=r.source_quote, mandatory=r.mandatory,
        needs_response=r.needs_response, page_limit=r.page_limit,
        changed_by_file_id=f.id if change_type else None, change_type=change_type,
    )
    s.add(req)
    return req


def extract_from_text(
    text: str, llm=None, progress: Callable[[str], None] | None = None,
) -> tuple[list[str], list[ExtractedRequirement]]:
    """Full requirement extraction for page-tagged solicitation text.

    Used by the app and by the evaluation harness (backend/evals), so the eval measures
    exactly what customers get. Returns (per-window summaries, requirements).
    """
    llm = llm or get_llm()
    progress = progress or (lambda _msg: None)
    extracted: list[ExtractedRequirement] = []
    summaries = []
    parts = windows(text, settings.extraction_window_chars)
    for i, w in enumerate(parts, start=1):
        progress(f"Extracting requirements: part {i} of {len(parts)}" if len(parts) > 1 else "Extracting requirements")
        result = llm.extract_requirements(w)
        summaries.append(result.summary)
        extracted.extend(result.requirements)

    # Second pass: keyword sweep for obligation sentences the model did not capture.
    uncovered = [(p, sent) for p, sent in obligation_sentences(text) if not _covered(sent, extracted)]
    if uncovered:
        progress(f"Double-checking {len(uncovered)} sentence(s) the first pass did not cover")
    for i in range(0, len(uncovered), 80):
        extracted.extend(llm.fill_gaps(uncovered[i : i + 80]).requirements)

    return summaries, _dedupe(extracted)


def _extract_base(s: Session, f: SolicitationFile, text: str, progress=None) -> None:
    bid = s.get(Bid, f.bid_id)
    seq = _next_sequence(s, f.bid_id)
    summaries, requirements = extract_from_text(text, progress=progress)
    for r in requirements:
        _add_requirement(s, f, r, seq)
        seq += 1
    if not bid.summary:
        bid.summary = " ".join(summaries[:2])[:3000]


def _tokens(t: str) -> set[str]:
    return {part for w in words(t) for part in w.split("-") if len(part) > 2}


def _covered(sentence: str, reqs: list[ExtractedRequirement], threshold: float = 0.6) -> bool:
    st = _tokens(sentence)
    if not st:
        return True
    for r in reqs:
        rt = _tokens(r.source_quote) | _tokens(r.text)
        if len(st & rt) / len(st) >= threshold:
            return True
    return False


def _dedupe(reqs: list[ExtractedRequirement]) -> list[ExtractedRequirement]:
    out: list[ExtractedRequirement] = []
    seen: list[set[str]] = []
    for r in reqs:
        t = _tokens(r.text)
        if any(t and len(t & o) / max(len(t | o), 1) > 0.85 for o in seen):
            continue
        seen.append(t)
        out.append(r)
    return out


def _apply_addendum(s: Session, f: SolicitationFile, text: str) -> None:
    reqs = s.scalars(
        select(Requirement).where(Requirement.bid_id == f.bid_id, Requirement.status != "removed")
        .order_by(Requirement.sequence)
    ).all()
    by_id = {r.id: r for r in reqs}
    listing = "\n".join(f"id={r.id} [{r.kind}] (page {r.page or '?'}) {r.text}" for r in reqs)
    result = get_llm().diff_addendum(listing, text)
    seq = _next_sequence(s, f.bid_id)
    for ch in result.changes:
        if ch.change_type == "added" and ch.requirement:
            _add_requirement(s, f, ch.requirement, seq, "added")
            seq += 1
            continue
        target = by_id.get(ch.requirement_id or -1)
        if target is None:
            continue
        target.changed_by_file_id, target.change_type = f.id, ch.change_type
        if ch.change_type == "removed":
            target.status = "removed"
        elif ch.change_type == "modified" and ch.requirement:
            r = ch.requirement
            target.text, target.kind, target.source_quote = r.text, r.kind, r.source_quote
            target.page, target.mandatory, target.needs_response = r.page, r.mandatory, r.needs_response
            target.page_limit = r.page_limit
            if target.status == "met":
                target.status = "open"
        if target.answer and target.answer.status not in ("queued", "failed"):
            target.answer.status = "stale"
    f.change_summary = result.summary


# ---------------------------------------------------------------- drafting


def queue_answers(s: Session, bid_id: int, requirement_ids: list[int] | None, force: bool) -> list[int]:
    """Mark answers queued and enqueue a draft job for each; returns the requirement ids."""
    q = select(Requirement).where(
        Requirement.bid_id == bid_id, Requirement.needs_response.is_(True), Requirement.status != "removed"
    )
    if requirement_ids:
        q = q.where(Requirement.id.in_(requirement_ids))
    out = []
    for r in s.scalars(q):
        a = r.answer
        if a and not force and a.status not in ("stale", "failed", "queued"):
            continue  # don't overwrite existing drafts or human work unless forced
        if a is None:
            a = Answer(org_id=r.org_id, requirement=r)
            s.add(a)
        a.status, a.error = "queued", None
        jobs.enqueue(s, r.org_id, "draft_answer", r.id)
        out.append(r.id)
    s.commit()  # answers and their jobs together
    return out


def draft_requirement(org_id: int, req_id: int, job: "jobs.JobRun | None" = None) -> None:
    with db.org_session(org_id) as s:
        req = s.get(Requirement, req_id)
        if req is None:
            return
        ans = req.answer or Answer(org_id=req.org_id, requirement=req)
        if ans.id is not None and ans.status not in ("queued", "drafting"):
            return  # someone edited or accepted it since it was queued: leave their work alone
        s.add(ans)
        ans.status = "drafting"
        s.commit()
        try:
            _draft(s, req, ans)
            s.commit()
        except Exception as e:
            s.rollback()
            req = s.get(Requirement, req_id)
            ans = req.answer or Answer(org_id=req.org_id, requirement=req)
            s.add(ans)
            if job and job.will_retry(e):
                ans.status, ans.error = "queued", _retry_note(job, e)
            else:
                ans.status, ans.error = "failed", str(e)[:2000]
            s.commit()
            raise


def _abandon_answer(org_id: int, req_id: int, message: str) -> None:
    with db.org_session(org_id) as s:
        req = s.get(Requirement, req_id)
        if req and req.answer:
            req.answer.status, req.answer.error = "failed", message
            s.commit()


jobs.register("ingest_document", ingest_document, _abandon_document)
jobs.register("process_file", process_solicitation_file, _abandon_file)
jobs.register("draft_answer", draft_requirement, _abandon_answer)


def _draft(s: Session, req: Requirement, ans: Answer) -> None:
    bid = req.bid
    hits = search(s, req.org_id, f"{req.section or ''} {req.text}", settings.retrieve_k)
    criteria = s.scalars(
        select(Requirement).where(
            Requirement.bid_id == bid.id, Requirement.kind == "evaluation",
            Requirement.status != "removed", Requirement.id != req.id,
        ).order_by(Requirement.sequence).limit(15)
    ).all()
    limits = s.scalars(
        select(Requirement).where(
            Requirement.bid_id == bid.id, Requirement.kind == "page_limit", Requirement.status != "removed"
        )
    ).all()
    context = "\n".join(
        x for x in [
            f'<solicitation title="{attr(bid.title)}" agency="{attr(bid.agency)}">',
            neutralize(bid.summary),
            "</solicitation>",
            "<evaluation_criteria>\n" + "\n".join(f"- {neutralize(c.text)}" for c in criteria) + "\n</evaluation_criteria>"
            if criteria else "",
            "<page_limits>\n" + "\n".join(f"- {neutralize(p.text)}" for p in limits) + "\n</page_limits>"
            if limits else "",
            f'<requirement kind="{attr(req.kind)}" section="{attr(req.section)}" page="{attr(req.page)}">',
            neutralize(req.text),
            f"Original wording: {neutralize(req.source_quote)}" if req.source_quote else "",
            "</requirement>",
            "Draft the proposal content that responds to this requirement.",
        ] if x
    )
    sources = "\n\n".join(
        f'<source number="{i}" from="{attr(h.chunk.label)}" page="{attr(h.chunk.page)}" '
        f'section="{attr(h.chunk.heading)}">\n{neutralize(h.chunk.text)}\n</source>'
        for i, h in enumerate(hits, start=1)
    ) or "(no matching sources found in the library)"

    result = get_llm().draft_answer(context, sources)

    ans.citations.clear()
    s.flush()
    verified = 0
    for c in result.citations:
        hit = hits[c.source_number - 1] if 1 <= c.source_number <= len(hits) else None
        ok = bool(hit and quote_in(c.quote, hit.chunk.text))
        verified += ok
        ans.citations.append(Citation(
            org_id=req.org_id,
            marker=c.marker, chunk_id=hit.chunk.id if hit else None, quote=c.quote, verified=ok,
            label=hit.chunk.label if hit else "Unknown source", page=hit.chunk.page if hit else None,
        ))

    conf, reasons = score(result.confidence, len(result.citations), verified, result.unsupported_claims, len(hits))
    ans.draft_text = result.answer
    ans.unsupported_claims = result.unsupported_claims
    ans.confidence = conf
    ans.confidence_reasons = reasons
    ans.error = None
    needs_review = conf < settings.review_threshold or result.unsupported_claims or verified < len(result.citations)
    ans.status = "needs_review" if needs_review else "drafted"
    if req.status == "open":
        req.status = "drafted"


def score(model_conf: float, n_cites: int, verified: int, unsupported: list[str], n_hits: int):
    reasons = []
    model_conf = min(max(model_conf, 0.0), 1.0)
    cite_ratio = verified / n_cites if n_cites else 0.0
    if n_cites == 0:
        reasons.append("No citations: nothing in the answer is backed by a source.")
    elif verified < n_cites:
        reasons.append(f"{n_cites - verified} of {n_cites} citations could not be verified against their source.")
    penalty = min(0.15 * len(unsupported), 0.45)
    if unsupported:
        reasons.append(f"{len(unsupported)} item(s) not supported by the library; placeholders inserted.")
    conf = 0.4 * model_conf + 0.6 * cite_ratio - penalty
    if n_hits == 0:
        reasons.append("No matching passages found in the library.")
        conf = min(conf, 0.2)
    return round(max(conf, 0.0), 2), reasons


def _norm(t: str) -> str:
    t = t.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    return " ".join(re.sub(r"[^\w\s$%.,'/-]", " ", t).split())


def quote_in(quote: str, source: str) -> bool:
    """True if the quote (allowing '...' elisions) appears in the source text."""
    src = _norm(source)
    parts = [p for p in (_norm(x) for x in re.split(r"\.\.\.|…", quote)) if len(p) >= 8]
    return bool(parts) and all(p.strip(" .,") in src for p in parts)


def strip_markers(text: str) -> str:
    return re.sub(r"\s?\[\d+(?:,\s*\d+)*\]", "", text)
