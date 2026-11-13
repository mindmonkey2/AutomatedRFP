# Requirement extraction evaluation

Missing a requirement is the costliest mistake an RFP tool can make: one missed form or page limit can get
a bid thrown out. This harness measures how many of a solicitation's requirements the app's extraction
pipeline finds, against answer keys labelled by hand.

It runs the same code the app uses (`app.pipeline.extract_from_text`: AI extraction, then the keyword
sweep and gap-filling pass), so the score reflects what users get.

## Run it

From `backend/`:

```bash
../.venv/bin/python -m evals.extraction                      # the configured provider (RFP_LLM_PROVIDER)
../.venv/bin/python -m evals.extraction --provider claude --model claude-sonnet-5-5 --effort medium
../.venv/bin/python -m evals.extraction --provider openai_compatible --model qwen3:32b \
    --base-url http://localhost:11434/v1                     # a self-hosted model (Ollama, vLLM, ...)
../.venv/bin/python -m evals.extraction --runner keyword     # no-AI baseline, free
../.venv/bin/python -m evals.extraction --min-recall 0.95    # exits 1 below 95% (use as a CI gate)
```

Each run writes a JSON and a Markdown report to `evals/results/`, including every missed requirement,
every trap the model fell for, and the estimated API cost of the run.

**Retrieval** (does the right library passage reach the drafting model?) has its own small eval:

```bash
pip install -r requirements-embeddings.txt
../.venv/bin/python -m evals.retrieval --database-url postgresql+psycopg://rfp:rfp@localhost:5432/rfp_test
../.venv/bin/python -m evals.retrieval --provider openai_compatible --model nomic-embed-text  # via Ollama
```

It loads `retrieval_cases.json` (26 passages, 28 questions, half worded differently from their answer)
into a temporary organization and compares keyword search with hybrid search (recall@1/3/5, MRR).

## What is measured

| Metric | Meaning |
| --- | --- |
| **Recall** | Share of labelled requirements found. The headline number; the target is 95%. |
| Mandatory recall | Recall on requirements whose omission could disqualify a bid. |
| Kind accuracy | Of found requirements, how many got the right type (form, deadline, ...). Some types overlap, so treat this as a secondary signal. |
| Page accuracy | Of found requirements, how many have the right page number. |
| Traps extracted | Sentences that sound like requirements but bind the owner, not the bidder ("The County shall provide..."). Lower is better. |
| Extracted items not in the answer key | Not automatically wrong (the key may be incomplete), but worth reading after each run. |

**Matching rule.** A labelled requirement counts as found when one extracted requirement covers at least
60% of the content words of its labelled quote (checking the extracted quote and restated text together).
Matching is one-to-one: an extracted item that lumps four forms together gets credit for one, because the
other three would be missing from the checklist.

## The cases

11 cases, 266 labelled requirements, 32 traps.

**Real US federal solicitations** (public domain; text stored in the repo; source links in each `gold.json`):

| Case | What it is | Requirements | Traps |
| --- | --- | --- | --- |
| `doe_nnsa_rfp_section_l` | DOE/NNSA RFP 89233220RNA000002 (Y-12 and Pantex management and operating contract, 2021), Section L pages 5-10: proposal structure, page limits, formatting, Volume I forms | 56 | 4 |
| `doe_nnsa_rfp_section_m` | The same RFP's complete Section M: evaluation criteria plus offeror obligations stated only there | 13 | 4 |
| `usace_1985_ifb_ocr` | US Army Corps of Engineers construction IFB DACW61-85-B-0039 (1985), special contract requirements from a scanned PDF with poor OCR; quotes keep the OCR errors | 16 | 4 |

**Real Indian government tenders** (text *not* stored in the repo, see below):

| Case | What it is | Requirements | Traps |
| --- | --- | --- | --- |
| `in_nhai_makhu_epc_2024` | NHAI highway EPC tender, NH-54 Makhu Town, Punjab (2024): complete e-tendering instructions (DSC, portal registration, bid security, integrity pact, GFR Rule 144(xi) certificate, local content, originals by post) | 32 | 3 |
| `in_esic_hyderabad_cpwd_2023` | ESIC building maintenance tender in CPWD percentage-rate format, Hyderabad (2023), pages 3-5: date table, CPWD/PWD registration, turnover, solvency, ESI/EPF/GST, EMD with MSE exemption; Telugu, Hindi and English on the same pages | 25 | 4 |
| `in_sai_bhopal_cladding_2020` | Sports Authority of India civil works tender on the CPP portal, Bhopal (2020), pages 4-5 and 19-20: justified text extracted one word per line, qualification table with interleaved columns | 22 | 3 |

Indian tenders state many mandatory rules with "should", "to be enclosed" or bare document lists
("Copy of EMD."), so a sweep for shall/must/required missed them (23-31% found). The current sweep
also reads these styles and finds 77-94% (see `results/baseline-keyword.md`; the v1 results are kept as
`results/baseline-keyword-v1.md`).

**Fetch-only cases.** Indian government works are copyrighted and tender documents are not clearly
covered by an open licence (GODL covers datasets), so for these cases the repo stores only the answer
key: short quotes, page numbers, the official source URL and the PDF's SHA-256. Rebuild the text locally
with:

```bash
../.venv/bin/python -m evals.fetch      # downloads from the official sites; text is git-ignored
```

Cases that have not been fetched are skipped (with a message), so tests and CI work without network
access. If a source PDF changes after labelling, `evals.fetch` warns and re-validates every quote.
Reports keep only counts, not extracted text, for these cases.

**Synthetic cases**, written for this evaluation to mirror common construction and public-sector
solicitations, so they can be labelled precisely:

| Case | What it is | Requirements | Traps |
| --- | --- | --- | --- |
| `k12_school_ifb` | School district invitation for bids (bid security, required forms, DVBE) | 20 | 4 |
| `county_cmar_rfp` | County construction-manager-at-risk RFP (tabbed content, page limits, scored criteria) | 24 | 2 |
| `federal_design_build` | Federal design-build, Sections L and M (volumes, SAM, small business, best value) | 25 | 1 |
| `water_main_srf_ifb` | City water main bid with state revolving fund rules (AIS, Davis-Bacon, DBE forms) | 14 | 2 |
| `university_ae_rfq` | University A/E qualifications (SF 330, no-fee rule, weighted criteria) | 19 | 1 |

Reports show recall separately for real and synthetic cases. Treat the real-case number as the more
honest one.

**Who labelled them.** All answer keys were labelled by Claude (AI-assisted), line by line against the
parser output, following the rules below; each `gold.json` records this in `labelled_by`. An independent
human review of the keys is still pending and would make the numbers more trustworthy. The real cases
are excerpts, not whole solicitations, to keep labelling precise; page numbers are the original PDF's.

## Adding a real solicitation

```bash
../.venv/bin/python -m evals.new_case path/to/rfp.pdf --id city_park_ifb --title "City of X — Park Pavilion IFB" --url https://...
```

This writes `cases/<id>/document.txt` and a draft `gold.json` pre-filled with every sentence that contains an
obligation word. Draft cases are skipped until a person reviews them and sets `"status": "reviewed"`.
Use public solicitations you are allowed to redistribute (US federal documents are public domain; check
terms for state and local ones).

## Labelling rules

1. **One requirement per distinct obligation on the bidder.** "Submit forms A, B, C and D" is four
   requirements. A sentence with a license requirement and a bonding requirement is two.
2. **Quote the shortest exact passage that identifies it.** The quote must appear word-for-word in
   `document.txt` (whitespace is ignored); `tests/test_evals.py` enforces this.
3. **Include obligations however they are phrased**: "shall", "must", "is required", imperatives
   ("Provide...", "Describe..."), schedule lines ("Proposals due: May 1"), and scoring tables.
4. **Owner obligations and rights are traps, not requirements** ("The District will...", "reserves the
   right to..."). So are permissions ("A bid may be withdrawn...").
5. **Kinds:** `submission`, `form`, `page_limit`, `format`, `deadline`, `evaluation`, `qualification`,
   `question` (same definitions as the extraction prompt in `app/llm.py`).
6. **mandatory** = missing it could make the bid non-responsive. Evaluation criteria and question
   deadlines are not mandatory. **needs_response** = the proposal must contain written content for it.
7. **page** = the `[Page N]` the quote appears on.
