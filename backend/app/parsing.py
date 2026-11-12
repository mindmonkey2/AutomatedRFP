"""Turn uploaded files into page-tagged text, and split text into retrievable chunks."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import settings

SUPPORTED = {".pdf", ".docx", ".xlsx", ".txt", ".md"}


class UnsupportedFile(ValueError):
    pass


@dataclass
class Page:
    number: int | None  # 1-based page for PDFs; None where the format has no pages
    text: str


@dataclass
class ParsedDoc:
    pages: list[Page]
    page_count: int | None = None
    empty_pages: list[int] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    def tagged_text(self) -> str:
        """Text with [Page N] markers so the model can report page numbers."""
        parts = []
        for p in self.pages:
            if not p.text.strip():
                continue
            parts.append(f"[Page {p.number}]\n{p.text}" if p.number else p.text)
        return "\n\n".join(parts)


class FileTooLarge(ValueError):
    pass


def _check_zip(path: Path) -> None:
    """DOCX and XLSX are zip archives; refuse ones that unpack to more than the limit (zip bombs)."""
    import zipfile

    try:
        with zipfile.ZipFile(path) as z:
            total = sum(i.file_size for i in z.infolist())
    except zipfile.BadZipFile as e:
        raise UnsupportedFile("This file is damaged or is not really a DOCX/XLSX file.") from e
    if total > settings.max_unzipped_mb * 1024 * 1024:
        raise FileTooLarge(f"This file unpacks to more than {settings.max_unzipped_mb} MB, which is not supported.")


def parse_file(path: Path) -> ParsedDoc:
    ext = path.suffix.lower()
    if ext in (".docx", ".xlsx"):
        _check_zip(path)
    if ext == ".pdf":
        return _parse_pdf(path)
    if ext == ".docx":
        return _parse_docx(path)
    if ext == ".xlsx":
        return _parse_xlsx(path)
    if ext in (".txt", ".md"):
        return ParsedDoc(pages=[Page(None, path.read_text(encoding="utf-8", errors="replace"))])
    raise UnsupportedFile(f"Unsupported file type {ext}. Use one of: {', '.join(sorted(SUPPORTED))}")


def _parse_pdf(path: Path) -> ParsedDoc:
    import pymupdf

    pages, empty = [], []
    with pymupdf.open(path) as doc:
        if doc.page_count > settings.max_pdf_pages:
            raise FileTooLarge(f"This PDF has {doc.page_count} pages; the limit is {settings.max_pdf_pages}. "
                               "Split it into parts.")
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            if len(text.strip()) < 20:
                empty.append(i)  # likely scanned; OCR is a later feature
            pages.append(Page(i, _clean(text)))
        count = doc.page_count
    return ParsedDoc(pages=pages, page_count=count, empty_pages=empty)


def _parse_docx(path: Path) -> ParsedDoc:
    import docx
    from docx.table import Table

    d = docx.Document(str(path))
    lines: list[str] = []
    # Body order matters: a table belongs under the heading it appears after.
    for block in d.iter_inner_content():
        if isinstance(block, Table):
            for row in block.rows:
                cells: list[str] = []
                seen: list = []  # cell XML elements (kept alive, compared by identity)
                for c in row.cells:
                    if any(c._tc is e for e in seen):  # a merged cell repeats once per column it spans
                        continue
                    seen.append(c._tc)
                    cells.append(c.text.strip())
                if any(cells):
                    lines.append(" | ".join(cells))
            continue
        t = block.text.strip()
        if not t:
            continue
        if block.style is not None and block.style.name.lower().startswith("heading"):
            lines.append(f"\n## {t}")
        else:
            lines.append(t)
    return ParsedDoc(pages=[Page(None, "\n".join(lines))])


def _parse_xlsx(path: Path) -> ParsedDoc:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    pages = []
    rows = 0
    for ws in wb.worksheets:
        lines = []
        for row in ws.iter_rows(values_only=True):
            rows += 1
            if rows > settings.max_sheet_rows:
                wb.close()
                raise FileTooLarge(f"This spreadsheet has more than {settings.max_sheet_rows:,} rows, "
                                   "which is not supported.")
            cells = ["" if v is None else str(v).strip() for v in row]
            if any(cells):
                lines.append(" | ".join(cells))
        if lines:
            pages.append(Page(None, f"## Sheet: {ws.title}\n" + "\n".join(lines)))
    wb.close()
    return ParsedDoc(pages=pages)


def _clean(text: str) -> str:
    text = text.replace("­", "")  # soft hyphens
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_HEADING = re.compile(r"^(#{1,6} .+|(\d+(\.\d+)*\.?|[A-Z]\.|SECTION \w+)\s+[A-Z][^\n]{2,120})$")


@dataclass
class TextChunk:
    text: str
    page: int | None
    heading: str | None


def chunk_pages(pages: list[Page], max_chars: int = 2000) -> list[TextChunk]:
    """Paragraph-packing chunker that keeps page numbers and the nearest heading."""
    chunks: list[TextChunk] = []
    heading: str | None = None
    for page in pages:
        buf: list[str] = []
        size = 0
        buf_heading = heading

        def flush():
            nonlocal buf, size
            body = "\n\n".join(buf).strip()
            if body:
                chunks.append(TextChunk(body, page.number, buf_heading))
            buf, size = [], 0

        for para in re.split(r"\n\s*\n", page.text):
            para = para.strip()
            if not para:
                continue
            first_line = para.splitlines()[0].strip()
            if _HEADING.match(first_line) and len(first_line) < 140:
                flush()
                heading = first_line.lstrip("# ").strip()
                buf_heading = heading
            while len(para) > max_chars:  # very long paragraph: hard split on sentence ends
                cut = para.rfind(". ", 0, max_chars)
                cut = cut + 1 if cut > max_chars // 2 else max_chars
                if size:
                    flush()
                buf, size = [para[:cut]], cut
                flush()
                para = para[cut:].strip()
            if size + len(para) > max_chars and buf:
                flush()
                buf_heading = heading
            buf.append(para)
            size += len(para) + 2
        flush()
    return chunks


# A word is a run of anything that is not whitespace or punctuation. Python's \w is not enough:
# it excludes combining marks, such as Hindi vowel signs, and would cut "निर्माण" into pieces.
WORD = re.compile(r"[^\s!-,./:-@\[-^`{-~\u00a0-\u00bf\u2000-\u206f\u0964\u0965\u3000-\u303f]+")


def words(text: str) -> list[str]:
    """Lower-cased words in any script (hyphens/underscores at the ends trimmed)."""
    return [w for w in (m.strip("-_") for m in WORD.findall(text.lower())) if any(c.isalnum() for c in w)]


_PAGE_MARK = re.compile(r"\[Page (\d+)\]")


def windows(text: str, max_chars: int) -> list[str]:
    """Split long text into windows on page/paragraph boundaries for extraction.

    A window that starts mid-page is prefixed with that page's [Page N] marker, so the model
    can still report correct page numbers for what it finds there.
    """
    if len(text) <= max_chars:
        return [text]
    out, start = [], 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            cut = text.rfind("\n[Page ", start + max_chars // 2, end)
            if cut == -1:
                cut = text.rfind("\n\n", start + max_chars // 2, end)
            if cut != -1:
                end = cut
        window = text[start:end]
        if start and not window.lstrip().startswith("[Page "):
            marks = _PAGE_MARK.findall(text, 0, start)
            if marks:
                window = f"[Page {marks[-1]}] (continued)\n" + window.lstrip("\n")
        out.append(window)
        start = end
    return out


# ---------------------------------------------------------------- obligation sweep
#
# A keyword safety net under the AI extraction: every sentence or checklist line that looks like
# something the bidder must do or submit. The AI pass re-reads whatever the extraction missed.
# It is tuned for both US-style solicitations ("shall", "must") and Indian government tenders
# (CPWD / NHAI style: "should", "to be enclosed", document checklists, NIT summary tables).

_OBLIGATION = re.compile(
    r"\b(shall|must|should|is required to|are required to|required|mandatory|has to|have to|needs? to"
    r"|(?:will|shall)? ?not (?:to )?be accepted|liable to be (?:summarily )?rejected|(?:shall|will) be rejected"
    r"|non[- ]?responsive|is to be ensured"
    r"|to be (?:enclosed|submitted|uploaded|furnished|attached|provided|deposited|produced|sent|scanned|signed)"
    r"|be enclosed|enclose[sd]?)\b",
    re.I,
)
# Checklist lines that name a document without any obligation word: "(a) Copy of EMD."
_DOCUMENT_ITEM = re.compile(
    r"^(?:if applicable,?\s*)?(?:(?:an? |the |original |self[- ]attested |scanned |duly )?"
    r"(?:cop(?:y|ies)|certificates?|affidavits?|undertakings?|letters? of|power of attorney|proof of"
    r"|self[- ]{0,2}certification|annexure|appendix|form\b|joint bidding agreement|bid security|emd|earnest money"
    r"|integrity pact|declaration|registration|audited|balance sheets?|solvency|details of|statement of)"
    r"|original\b)",
    re.I,
)
_DATE = re.compile(
    r"\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}"
    r"|\d{1,2}(?:st|nd|rd|th)? (?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*,? \d{4}"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2},? \d{4})\b",
    re.I,
)
_DEADLINE_WORD = re.compile(r"\b(last|due|end|closing|before|latest|deadline|submission|pre[- ]?bid|queries)\b", re.I)
_PERIOD = re.compile(
    r"\b(period|validity|within)\b.*?\b(\d+|one|two|three|four|five|six|seven|ten|fifteen|thirty)"
    r"\s*(working )?(days?|weeks?|months?|years?)\b",
    re.I,
)
# What the procuring authority does or may do is not a bidder requirement (a "trap").
_AUTHORITY_ACTION = re.compile(
    r"reserves? the right"
    r"|^(?:the )?(?:authority|owner|employer|department|corporation|government|purchaser|competent authority"
    r"|tender inviting authority|engineer[- ]in[- ]charge)\b[^.]{0,40}\b(?:shall|will|may)\b"
    r"|\b(?:shall|will) be (?:opened|hosted|returned|refunded|intimated|notified|published)\b",
    re.I,
)
# List markers: 1.  (a)  a)  (iv)  iv.  A.  •  -
_MARKER = re.compile(r"^(?:\(?(?:\d{1,2}|[ivxlc]{1,6}|[a-z])[.)]|\((?:\d{1,2}|[ivxlc]{1,6}|[a-z])\)|[•▪●◦*–-])(?=\s|$)\s*", re.I)
# A lead-in whose list items are all requirements: "The bid shall become invalid if:",
# "The list of documents to be scanned and uploaded ...:"
_LEAD_IN = re.compile(r"(?:invalid|rejected|disqualified|non[- ]?responsive)\s+if\s*:?$|:$")
_VALUE_START = re.compile(r"^(?:\d|rs\.?\s|₹|inr\b|within\b|up ?to\b)", re.I)
# A line ending in one of these words is mid-sentence, so a list marker after it is inline.
_OPEN_END = re.compile(r"\b(?:to|and|or|of|the|a|an|by|with|for|be|shall|must|will|in|on|that|following)$", re.I)
_SHORT_LINE = 60  # wrapped prose lines are longer; shorter lines end a heading, row or item
_ABBREV = re.compile(r"\b(?:rs|no|nos|mr|ms|dr|sl|viz|etc|co|ltd|pvt|st|vol|cl|sub|para|i\.e|e\.g|[a-z])\.$", re.I)


def _logical_lines(block: str) -> list[tuple[str, bool]]:
    """Undo PDF hard wrapping. Returns (text, starts_with_list_marker) units: wrapped lines of one
    sentence are joined, while list items, headings and short table cells stay separate, and a
    short label is joined with the value on the next line ("Period of Completion" + "12 Months")."""
    units: list[tuple[str, bool]] = []
    cur, cur_item, prev = "", False, ""
    for raw in block.split("\n"):
        line = raw.strip()
        if not line:
            if cur:
                units.append((cur, cur_item))
            cur, cur_item, prev = "", False, ""
            continue
        is_item = bool(_MARKER.match(line))
        if cur:
            if _MARKER.fullmatch(prev):  # a marker on its own line belongs to the text after it
                new_unit = False
            elif is_item:
                # "...shall be required to (a) commence..., (b) complete..." is one inline list.
                new_unit = not _OPEN_END.search(prev)
            elif line[0].islower() or _OPEN_END.search(prev):  # the sentence continues
                new_unit = False
            elif len(prev) < _SHORT_LINE and len(line) < _SHORT_LINE and _VALUE_START.match(line) \
                    and not _OBLIGATION.search(prev):
                new_unit = False  # label + value in a summary table
            else:
                new_unit = prev.endswith((".", ";", ":", "?", "!")) or len(prev) < _SHORT_LINE
            if new_unit:
                units.append((cur, cur_item))
                cur, cur_item = "", False
        if not cur:
            cur_item = is_item
        cur = f"{cur} {line}".strip()
        prev = line
    if cur:
        units.append((cur, cur_item))
    return units


def _sentences(unit: str) -> list[str]:
    """Split a unit into sentences, without breaking at abbreviations like "Rs." or "No."."""
    parts = re.split(r"(?<=[.;?!])\s+(?=[A-Z(\[\"“‘])|(?<=:)\s+(?=[A-Z])", unit)
    out: list[str] = []
    for p in parts:
        if out and _ABBREV.search(out[-1]):
            out[-1] = f"{out[-1]} {p}"
        else:
            out.append(p)
    return out


def obligation_sentences(text: str) -> list[tuple[int | None, str]]:
    """Keyword sweep: (page, sentence) for every sentence or checklist line that looks like a
    bidder requirement: obligation wording, a listed document, or a dated deadline / period."""
    out: list[tuple[int | None, str]] = []
    page = None
    in_required_list = False  # inside the items of a lead-in like "The bid shall become invalid if:"
    for block in re.split(r"(\[Page \d+\])", text):
        m = re.fullmatch(r"\[Page (\d+)\]", block)
        if m:
            page = int(m.group(1))
            continue
        for unit, is_item in _logical_lines(block):
            body = _MARKER.sub("", unit, count=1) if is_item else unit
            listed = is_item and in_required_list
            if not is_item:
                flat = " ".join(unit.split())
                in_required_list = bool(_LEAD_IN.search(flat)) and bool(
                    _OBLIGATION.search(flat) or re.search(r"\b(?:invalid|rejected|disqualified)\b", flat, re.I))
            for sent in _sentences(body):
                s = " ".join(sent.split())
                if not 10 <= len(s) <= 600 or _AUTHORITY_ACTION.search(s):
                    continue
                if (
                    (len(s) >= 25 and _OBLIGATION.search(s))
                    or (is_item and _DOCUMENT_ITEM.match(s))
                    or listed
                    or (len(s) <= 200 and _DATE.search(s) and _DEADLINE_WORD.search(s))
                    or (len(s) <= 200 and _PERIOD.search(s))
                ):
                    out.append((page, s))
    return out
