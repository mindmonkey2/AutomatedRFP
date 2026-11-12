"""Turn uploaded files into page-tagged text, and split text into retrievable chunks."""

import re
from dataclasses import dataclass, field
from pathlib import Path

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


def parse_file(path: Path) -> ParsedDoc:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _parse_pdf(path)
    if ext == ".docx":
        return _parse_docx(path)
    if ext == ".xlsx":
        return _parse_xlsx(path)
    if ext in (".txt", ".md"):
        return ParsedDoc(pages=[Page(None, path.read_text(errors="replace"))])
    raise UnsupportedFile(f"Unsupported file type {ext}. Use one of: {', '.join(sorted(SUPPORTED))}")


def _parse_pdf(path: Path) -> ParsedDoc:
    import pymupdf

    pages, empty = [], []
    with pymupdf.open(path) as doc:
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
    for ws in wb.worksheets:
        lines = []
        for row in ws.iter_rows(values_only=True):
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


_OBLIGATION = re.compile(r"\b(shall|must|is required to|are required to|required|mandatory|will not be accepted)\b", re.I)


def obligation_sentences(text: str) -> list[tuple[int | None, str]]:
    """Keyword sweep: every sentence containing an obligation word, with its page."""
    out = []
    page = None
    for block in re.split(r"(\[Page \d+\])", text):
        m = re.fullmatch(r"\[Page (\d+)\]", block)
        if m:
            page = int(m.group(1))
            continue
        for sent in re.split(r"(?<=[.;:])\s+|\n(?=[A-Z0-9•\-])", block):
            s = " ".join(sent.split())
            if 25 <= len(s) <= 600 and _OBLIGATION.search(s):
                out.append((page, s))
    return out
