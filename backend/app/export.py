"""Exports: DOCX response draft, XLSX compliance matrix, and a submission-readiness check."""

import io
import math
import re

from .models import Bid, Requirement
from .pipeline import strip_markers

WORDS_PER_PAGE = 500  # rough single-spaced estimate used for page-limit warnings


def answer_text(req: Requirement) -> str | None:
    a = req.answer
    if a is None:
        return None
    text = a.final_text or a.draft_text
    return strip_markers(text) if text else None


def response_requirements(bid: Bid) -> list[Requirement]:
    return [r for r in bid.requirements if r.needs_response and r.status != "removed"]


def readiness(bid: Bid) -> dict:
    active = [r for r in bid.requirements if r.status != "removed"]
    resp = response_requirements(bid)
    missing_answers = [r for r in resp if not answer_text(r)]
    unreviewed = [
        r for r in resp if r.answer and r.answer.status in ("drafted", "needs_review", "stale", "failed")
    ]
    open_mandatory = [r for r in active if r.mandatory and r.status in ("open", "drafted") and not r.needs_response]
    placeholders = [r for r in resp if (t := answer_text(r)) and "[[TBD" in t]
    unverified_facts = [r for r in resp if r.answer and any(
        f["problem"] == "not_in_sources" for f in (r.answer.fact_issues or []))]
    words = sum(len((answer_text(r) or "").split()) for r in resp)
    est_pages = math.ceil(words / WORDS_PER_PAGE) if words else 0
    limits = [r.page_limit for r in active if r.kind == "page_limit" and r.page_limit]
    overall_limit = max(limits) if limits else None

    issues = []
    if missing_answers:
        issues.append(f"{len(missing_answers)} response item(s) have no answer yet.")
    if unreviewed:
        issues.append(f"{len(unreviewed)} answer(s) are not reviewed (drafted, needs review, stale or failed).")
    if placeholders:
        issues.append(f"{len(placeholders)} answer(s) still contain [[TBD]] placeholders.")
    if open_mandatory:
        issues.append(f"{len(open_mandatory)} mandatory item(s) (forms, format, deadlines) are not marked met.")
    # A warning, not a blocker: a reviewer may knowingly add a fact the library does not hold yet.
    warnings = []
    if unverified_facts:
        warnings.append(f"{len(unverified_facts)} answer(s) state figures or names that are not in any cited "
                        "source. Check them before submitting.")
    if overall_limit and est_pages > overall_limit:
        issues.append(f"Estimated length {est_pages} pages exceeds the {overall_limit}-page limit.")

    def ids(rs):
        return [r.id for r in rs]

    return {
        "ready": not issues,
        "issues": issues,
        "warnings": warnings,
        "unverified_fact_ids": ids(unverified_facts),
        "requirements_total": len(active),
        "response_items": len(resp),
        "missing_answer_ids": ids(missing_answers),
        "unreviewed_ids": ids(unreviewed),
        "placeholder_ids": ids(placeholders),
        "open_mandatory_ids": ids(open_mandatory),
        "estimated_pages": est_pages,
        "page_limit": overall_limit,
    }


def export_docx(bid: Bid) -> bytes:
    import docx
    from docx.shared import Pt

    d = docx.Document()
    d.styles["Normal"].font.size = Pt(11)
    d.add_heading(bid.title, level=0)
    if bid.agency:
        d.add_paragraph(f"Submitted to: {bid.agency}")
    current_section = None
    for r in response_requirements(bid):
        if r.section and r.section != current_section:
            current_section = r.section
            d.add_heading(r.section, level=1)
        d.add_heading(_short(r.text), level=2)
        text = answer_text(r)
        if text:
            for para in re.split(r"\n\s*\n", text.strip()):
                d.add_paragraph(para.strip())
        else:
            d.add_paragraph("[[TBD: no answer drafted yet]]")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def export_matrix_xlsx(bid: Bid) -> bytes:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Compliance matrix"
    headers = ["#", "Requirement", "Kind", "Section", "Page", "Mandatory", "Status",
               "Answer status", "Confidence", "Assignee", "Addendum change", "Source quote"]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F4E79")
    for r in bid.requirements:
        a = r.answer
        ws.append([
            r.sequence, r.text, r.kind, r.section, r.page, "Yes" if r.mandatory else "No", r.status,
            a.status if a else ("n/a" if not r.needs_response else "not started"),
            a.confidence if a else None, a.assignee if a else None, r.change_type, r.source_quote,
        ])
    widths = [5, 70, 14, 24, 7, 10, 10, 14, 11, 16, 14, 70]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _short(text: str, n: int = 120) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"
