# Requirement extraction evaluation

Missing a requirement is the costliest mistake an RFP tool can make: one missed form or page limit can get
a bid thrown out. This harness measures how many of a solicitation's requirements the app's extraction
pipeline finds, against answer keys labelled by hand.

It runs the same code the app uses (`app.pipeline.extract_from_text`: AI extraction, then the keyword
sweep and gap-filling pass), so the score reflects what users get.

## Run it

From `backend/`:

```bash
../.venv/bin/python -m evals.extraction                      # Claude, using RFP_MODEL / RFP_EFFORT
../.venv/bin/python -m evals.extraction --model claude-sonnet-5-5 --effort medium
../.venv/bin/python -m evals.extraction --runner keyword     # no-AI baseline, free
../.venv/bin/python -m evals.extraction --min-recall 0.95    # exits 1 below 95% (use as a CI gate)
```

Each run writes a JSON and a Markdown report to `evals/results/`, including every missed requirement,
every trap the model fell for, and the estimated API cost of the run.

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

| Case | Type | Requirements | Traps |
| --- | --- | --- | --- |
| `k12_school_ifb` | School district invitation for bids (bid security, required forms, DVBE) | 20 | 4 |
| `county_cmar_rfp` | County construction-manager-at-risk RFP (tabbed content, page limits, scored criteria) | 24 | 2 |
| `federal_design_build` | Federal design-build, Sections L and M (volumes, SAM, small business, best value) | 25 | 1 |
| `water_main_srf_ifb` | City water main bid with state revolving fund rules (AIS, Davis-Bacon, DBE forms) | 14 | 2 |
| `university_ae_rfq` | University A/E qualifications (SF 330, no-fee rule, weighted criteria) | 19 | 1 |

These five are **synthetic**: written for this evaluation to mirror common solicitation structures, so they
can be labelled precisely and published freely. They deliberately include requirements phrased without
"shall" or "must" (instructions, schedule tables, scoring tables) and owner obligations as traps. Real
public solicitations should be added next (see below); results on synthetic cases alone overstate how
well extraction works on messy real documents.

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
