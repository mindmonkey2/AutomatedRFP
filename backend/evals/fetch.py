"""Download source documents for cases whose text is not stored in the repo.

Some public solicitations (for example Indian government tenders) are publicly posted
but not clearly licensed for redistribution. For those cases the repo keeps only the
answer key (short quotes, page numbers, source URL) and this command rebuilds the
document text locally from the official source:

    ../.venv/bin/python -m evals.fetch            # fetch every case that is missing
    ../.venv/bin/python -m evals.fetch --force    # re-download everything

A case's gold.json has a "fetch" block: {"url": ..., "pages": [...], "sha256": ...}.
The text is written to document.fetched.txt (git-ignored). If the PDF at the URL has
changed since it was labelled, the checksum differs and the quotes are re-validated.
"""

import argparse
import hashlib
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

from app.parsing import parse_file

from .dataset import CASES_DIR, FETCHED_NAME, load_case, validate

USER_AGENT = "Mozilla/5.0 (compatible; rfp-engine-eval/0.1)"


def fetch_case(folder: Path, force: bool = False) -> str:
    gold = json.loads((folder / "gold.json").read_text())
    spec = gold.get("fetch")
    if not spec:
        return "skip"
    out = folder / FETCHED_NAME
    if out.exists() and not force:
        return "present"
    with tempfile.TemporaryDirectory(prefix="rfp-fetch-") as tmp:
        pdf = Path(tmp) / "source.pdf"
        req = urllib.request.Request(spec["url"], headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as resp:
            pdf.write_bytes(resp.read())
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if not pdf.read_bytes().startswith(b"%PDF"):
            raise RuntimeError(f"{spec['url']} did not return a PDF")
        parsed = parse_file(pdf)
    pages = set(spec.get("pages") or [p.number for p in parsed.pages])
    text = "\n\n".join(f"[Page {p.number}]\n{p.text}" for p in parsed.pages
                       if p.number in pages and p.text.strip())
    out.write_text(text + "\n")
    note = "" if digest == spec.get("sha256") else " (WARNING: source PDF changed since labelling)"
    problems = validate(load_case(folder))
    if problems:
        return "fetched with answer-key problems" + note + ":\n    " + "\n    ".join(problems)
    return "fetched" + note


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="re-download even if the text is present")
    ap.add_argument("--cases", help="comma-separated case ids")
    args = ap.parse_args(argv)
    ids = set(args.cases.split(",")) if args.cases else None
    failed = False
    for folder in sorted(CASES_DIR.iterdir()):
        if not (folder / "gold.json").exists() or (ids and folder.name not in ids):
            continue
        try:
            status = fetch_case(folder, args.force)
        except Exception as e:  # noqa: BLE001 - report and continue with the other cases
            status, failed = f"FAILED: {e}", True
        if status != "skip":
            print(f"{folder.name}: {status}")
            failed |= "problems" in status
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
