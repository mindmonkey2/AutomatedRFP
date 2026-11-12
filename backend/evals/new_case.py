"""Turn a real solicitation into a new eval case with a DRAFT answer key.

    ../.venv/bin/python -m evals.new_case path/to/rfp.pdf --id city_park_ifb \\
        --title "City of X — Park Pavilion IFB" --url https://example.gov/bid/123

Writes evals/cases/<id>/document.txt (page-tagged text, same as the app sees) and
gold.json with status "draft". The draft lists every sentence containing an
obligation word as a candidate. A person must then:
  1. delete candidates that are not bidder requirements (move owner obligations to "traps"),
  2. split candidates that hold several obligations, trim each quote to the requirement,
  3. add requirements phrased without obligation words ("Include...", "Provide..."),
  4. set kind / mandatory / needs_response / page, then set "status": "reviewed".
See evals/README.md for the labelling rules. Only reviewed cases are scored.
"""

import argparse
import json
import sys
from pathlib import Path

from app.parsing import obligation_sentences, parse_file

from .dataset import CASES_DIR


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", type=Path)
    ap.add_argument("--id", required=True, help="folder name, e.g. city_park_ifb")
    ap.add_argument("--title", required=True)
    ap.add_argument("--url", help="where the public solicitation was downloaded from")
    args = ap.parse_args(argv)

    folder = CASES_DIR / args.id
    if folder.exists():
        print(f"{folder} already exists", file=sys.stderr)
        return 2
    parsed = parse_file(args.file)
    text = parsed.tagged_text()
    if parsed.empty_pages:
        print(f"Warning: pages without text (scanned?): {parsed.empty_pages}", file=sys.stderr)

    candidates = [
        {"id": f"R{i:03d}", "kind": "submission", "page": p, "mandatory": True, "needs_response": False, "quote": s}
        for i, (p, s) in enumerate(obligation_sentences(text), start=1)
    ]
    folder.mkdir(parents=True)
    (folder / "document.txt").write_text(text + "\n")
    gold = {"id": args.id, "title": args.title, "source": "real", "source_url": args.url, "status": "draft",
            "notes": "DRAFT: candidates from the keyword sweep. Review every item before setting status to reviewed.",
            "requirements": candidates, "traps": []}
    (folder / "gold.json").write_text(json.dumps(gold, indent=2, ensure_ascii=False) + "\n")
    print(f"Created {folder} with {len(candidates)} draft candidates. Review gold.json before use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
