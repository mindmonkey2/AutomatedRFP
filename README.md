# RFP Engine

[![CI](https://github.com/mindmonkey2/AutomatedRFP/actions/workflows/ci.yml/badge.svg)](https://github.com/mindmonkey2/AutomatedRFP/actions/workflows/ci.yml)

**A compliance-first AI workspace for answering RFPs, built for construction firms and government contractors.**

Upload a solicitation and RFP Engine lists every requirement in it, tracks every addendum, and
drafts each answer from your company's own past proposals, project records and certificates. Every
claim cites its source, and a person approves each answer before it goes out.

> Status: working MVP (v0.1). Suitable for pilots with design partners, not yet for public production use.
> See [What's built and what's next](#whats-built-and-whats-next).

---

## The problem

Public agencies and project owners award big contracts through formal solicitations (RFPs, RFQs,
IFBs). Responding is slow, repetitive and risky:

- **It takes a long time.** A typical response takes a bid team 20 to 40 hours, much of it spent
  digging through old proposals, résumés, project sheets and certificates for answers they have
  written before.
- **One mistake can sink the bid.** Solicitations run 50 to 300+ pages. A missed form, a page limit
  exceeded or an expired insurance certificate can get a bid rejected as "non-responsive" before
  anyone reads it.
- **Requirements move.** Addenda change deadlines, scopes and required forms partway through, and
  someone has to work out what changed and which answers it affects.
- **Knowledge walks out the door.** The best answers live in one person's folders or memory.

## What RFP Engine does

| Step | Without RFP Engine | With RFP Engine |
| --- | --- | --- |
| Read the solicitation | Someone reads 100+ pages and builds a compliance checklist by hand | Every requirement, form, page limit, format rule, deadline and evaluation criterion is extracted into a compliance matrix, each linked to its page and exact wording |
| Handle addenda | Re-read and compare by hand | Each addendum is compared with the matrix: requirements are marked added, changed or removed, and affected answers are flagged for review |
| Find past answers | Search shared drives and email; ask colleagues | The library is searched automatically for the most relevant passages from past proposals, project records and credentials |
| Write the first draft | Copy, paste and rewrite for hours | A first draft of each section, written against the evaluation criteria, with a citation on every claim |
| Check facts | Hope nothing is out of date | Each citation is checked against its source text. Low-confidence answers and gaps are flagged, with `[[TBD]]` placeholders instead of invented facts |
| Track certificates | Spreadsheet, if anyone remembers | Licenses, bonds, insurance and certifications with a warning 30 days before expiry |
| Final check | Manual checklist | A readiness report lists unanswered items, unreviewed answers, leftover placeholders, unmet mandatory items and length against the page limit |
| Submit | Assemble documents by hand | Export the response as Word and the compliance matrix as Excel |
| Next bid | Start over | Approved answers go back into the library, so every bid makes the next one faster |

## How it saves time, effort and money

**Time.** The slowest parts of a bid are building the compliance checklist, finding past content and
writing the first draft. RFP Engine does those in minutes, so the team's hours go to the parts that win
bids: strategy, pricing and tailoring the story to the owner.

**Effort.** Bid work is deadline-driven and draining. Taking over the search-and-copy work and the
checklist anxiety reduces late nights before due dates. Subject-matter experts only review the questions
routed to them instead of writing from scratch.

**Money.** Fewer hours per bid means either lower cost per bid or more bids with the same team. Fewer
compliance mistakes means fewer bids thrown out on a technicality after the work is already spent.

### Worked example (plug in your own numbers)

These figures are **illustrative assumptions**, not measured results. Pilots should measure the real numbers.

| Input | Example value |
| --- | --- |
| Bids per month | 8 |
| Hours per bid today | 30 |
| Loaded cost per bid-team hour | $75 |
| **Current monthly bid effort** | 8 × 30 × $75 = **$18,000** |
| Assumed reduction in hours with RFP Engine | 50% |
| **Monthly effort saved** | **$9,000** (120 hours) |
| Subscription (Team tier, planned) | $500 |

The same 120 hours could instead go into 4 extra bids a month at today's workload. A single extra
contract won, or one disqualification avoided, can easily be worth more than a year of subscription.

## Who it's for

- **General contractors and specialty subcontractors** bidding public works and private projects
- **Architecture and engineering firms** answering qualification-based selections (RFQs, SF-330s)
- **Government contractors** (roughly 10 to 500 staff) answering federal, state and local solicitations
- **Small firms without a proposal team**, where the owner or estimator writes every bid

Typical uses:

- Responding to RFPs, RFQs, IFBs and statements of qualifications
- Prequalification packages and vendor registration questionnaires
- Security and compliance questionnaires (anything with a list of questions)
- Building a searchable, citable company knowledge base from years of past bids
- Keeping licenses, bonds, insurance and certifications current

## How it works

```mermaid
flowchart LR
    A[Library<br/>past proposals, projects,<br/>credentials] --> D
    B[Solicitation<br/>+ addenda] --> C[Compliance matrix<br/>every requirement,<br/>with page + quote]
    C --> D[Draft with citations<br/>search library, write to<br/>evaluation criteria]
    D --> E{Confidence<br/>check}
    E -- low / gaps --> F[Needs review<br/>routed to an expert]
    E -- high --> G[Drafted]
    F --> H[Review and approve]
    G --> H
    H --> I[Export<br/>Word response +<br/>Excel matrix]
    H -- approved answers --> A
```

1. **Ingest.** Files (PDF, Word, Excel, text) are parsed into passages that keep their page numbers
   and headings, and indexed for full-text search. Project records and credentials are indexed too.
2. **Extract requirements.** The solicitation is read in sections. The AI returns structured
   requirements (type, page, verbatim quote, mandatory or not, needs a written answer or not). A second
   pass scans for every "shall", "must" and "required" sentence the first pass did not capture and
   sends those back for review, because a missed requirement is the costliest error.
3. **Diff addenda.** Each addendum is compared with the current requirements to produce a list of
   changes, which is applied to the matrix. Answers touched by a change are marked stale.
4. **Draft.** For each item that needs a written answer, the best-matching passages are retrieved and
   the AI writes a response using only those sources, against the bid's evaluation criteria and page
   limits. Every claim carries a citation marker.
5. **Verify and score.** Each citation's quote is checked against the source passage. Confidence
   combines the model's own estimate, the share of verified citations and the number of unsupported
   items. Anything below the threshold, or with unverified citations or placeholders, goes to "needs review".
6. **Review and learn.** People edit, assign, accept and approve. Approved answers become library
   passages for future bids.

### Why you can trust the drafts

- The AI is instructed to use only your sources and never invent names, numbers, dates or license numbers.
- Every citation is machine-checked against the source text and shown as "verified" or "not found in source".
- Gaps become visible `[[TBD]]` placeholders, and the readiness check blocks on them.
- Nothing is approved without a person.

## Design notes

**Is this a RAG system?** Partly. Drafting is retrieval-augmented generation: for each requirement the
system retrieves the most relevant passages from the company's library and the model writes only from
those passages. Requirement extraction and addendum diffing are not RAG: the model reads the
solicitation itself, section by section, and returns structured data.

**How hallucination is controlled** (layers, from prevention to detection to human review):

| Layer | What it does | Where |
| --- | --- | --- |
| Grounding | The model sees only retrieved passages and is told to use nothing else | `pipeline._draft`, `llm.DRAFT_SYSTEM` |
| Structured output | Responses must match a schema (answer, citations with quotes, unsupported items, confidence) | `llm.py` schemas |
| Explicit gaps | Missing facts become `[[TBD: ...]]` placeholders, listed as unsupported, never invented | `llm.DRAFT_SYSTEM` |
| Citation check | Each cited quote must appear in the passage it points to, or it is marked "not found in source" | `pipeline.quote_in` |
| Confidence routing | Unverified citations, placeholders or low confidence send the answer to review | `pipeline.score` |
| Verbatim requirements | Each extracted requirement carries the exact quote and page, so a reviewer can check it at a glance | `ExtractedRequirement` |
| Recall safety net | A keyword sweep re-checks what the first extraction missed: obligation wording (US "shall/must", Indian "should/to be enclosed"), document checklists, and deadline rows, with PDF line wrapping undone | `parsing.obligation_sentences` |
| Human approval | Nothing is approved or exported as final without a person | review screen, readiness check |

Known limits: the citation check confirms that a quote exists in the source, not that the sentence
around it says the same thing. A planned second check will ask a separate model call whether each
claim is fully supported by its passage.

## Measuring accuracy

A missed requirement is the costliest error, so extraction is measured, not assumed. The evaluation
harness in [`backend/evals`](backend/evals/README.md) runs the app's real extraction pipeline on
solicitations with hand-labelled answer keys and reports recall, mandatory recall, type and page
accuracy, how many owner-obligation "traps" were wrongly extracted, and the API cost of the run.

The test set has **11 cases and 266 labelled requirements**:

- **6 real solicitations:** a 2021 DOE/NNSA RFP's Section L and Section M; a scanned 1985 Army Corps of
  Engineers construction bid with messy OCR; and three Indian government tenders (an NHAI highway EPC
  tender, an ESIC building tender in CPWD format with Telugu and Hindi on the page, and a Sports Authority
  of India tender from the CPP portal)
- **5 synthetic** construction and public-sector solicitations

Indian tender text is not redistributed: the repo keeps only the answer keys, and `python -m evals.fetch`
rebuilds the documents locally from the official sites.

| Extractor | Recall, all cases | Recall, real cases | Mandatory recall | Traps extracted |
| --- | --- | --- | --- | --- |
| Keyword sweep v1 (shall/must/required only) | 49.2% (131/266) | 46.3% (76/164) | 52.7% | 8 of 32 |
| Keyword sweep v2 (current, no AI) | 71.8% (191/266) | 80.5% (132/164) | 77.1% | 3 of 32 |
| Claude pipeline (`claude-opus-5-5`) | not yet run | | | |
| Self-hosted model (any OpenAI-compatible server) | not yet run | | | |
| **Target** | **95%** | | | |

The first keyword sweep found only 23-31% of the requirements in the Indian tenders, which say "should"
and "to be enclosed" and list documents with no obligation word at all, in PDFs whose hard line breaks
cut sentences in half. Version 2 undoes the line wrapping and reads checklists, "invalid if:" lists and
summary-table rows, finding 92% (ESIC) and 94% (NHAI). The third Indian tender (SAI Bhopal) was held out
while the rules were written and went from 23% to 77%. It also skips more buyer obligations (3 traps instead
of 8) and flags fewer false positives (34% of its items are not in the answer key, down from 40%). It still
misses most instructions ("Describe...", "Provide...") and evaluation criteria: that is the gap the AI
pass has to close. Run it yourself with
`../.venv/bin/python -m evals.extraction` from `backend/` (needs `ANTHROPIC_API_KEY`).
Answer keys were labelled with AI assistance; independent human review is pending.

## Security and data isolation

- **Sign-in:** email and password (Argon2id hashing), server-side sessions in an httpOnly cookie,
  logout revokes the session, failed-login rate limiting (per account, and per visitor address when a
  trusted reverse proxy reports it), invite links for teammates, admin and member roles.
- **Isolation between companies, enforced twice:** every query filters by organization, **and**
  Postgres row-level security hides other organizations' rows even if a query forgets the filter. With
  no organization bound, customer tables return nothing (fail closed). Tests verify both layers.
- **Cross-site request protection:** SameSite cookies plus an Origin check on every write.
- **Browser hardening:** a Content Security Policy (scripts, styles and API calls only from the app
  itself, no embedding in other sites), no-referrer handling so invite links never leak, and API
  responses marked never to be cached.
- **Untrusted documents:** solicitations and library files are written by outside parties, so their
  text is escaped before it goes into a prompt (it cannot close a prompt section or pose as another
  source), and every prompt tells the model to analyse that text, never to follow instructions in it.
- **Upload limits:** files are streamed to disk (50 MB cap) and refused if they expand too far: PDF
  page count, spreadsheet rows, and the unpacked size of DOCX/XLSX files (zip bombs).
- **Continuous integration:** every push runs the test suite against a real Postgres (as a non-superuser,
  so row-level security is enforced), checks the models against the migrations, builds the frontend, and
  audits Python and npm dependencies for known vulnerabilities (also weekly).
- **Your data and the AI:** documents are sent to the configured AI provider only to process your own
  bids. With Claude, the API does not train on API data by default. With a self-hosted model, nothing
  leaves your servers.

## What's built and what's next

| Area | Status |
| --- | --- |
| Library ingest (PDF, DOCX, XLSX, TXT), project records, credentials with expiry alerts | Built |
| Compliance matrix extraction with gap-filling pass | Built |
| Addendum diffing and stale-answer flags | Built |
| Cited drafting, citation verification, confidence scoring, review queue | Built |
| Review, assignment, approval back into the library (saved answers can be viewed and removed) | Built |
| Word and Excel export, readiness check | Built |
| Sign-in, organizations, invites, roles | Built |
| Postgres with migrations, full-text search, row-level security | Built |
| Choice of AI provider: Claude or self-hosted models via any OpenAI-compatible server | Built |
| Semantic search (pgvector) alongside full-text search | Planned |
| Durable job queue (jobs currently run inside the API process) | Planned |
| OCR for scanned PDFs | Planned |
| Filling the customer's own Excel questionnaire in place; fillable PDF forms | Planned |
| Email delivery of invites and expiry alerts; password reset; SSO | Planned |
| Bid/no-bid scoring, SAM.gov monitoring, win/loss learning | Later |
| Requirement-extraction evaluation: 11 labelled cases (3 US federal, 3 Indian, 5 synthetic), keyword baseline | Built |
| Claude score on the eval set; human review of answer keys; more real solicitations | Next |

## AI providers: Claude or your own models

RFP Engine runs on either of two providers, chosen per deployment with `RFP_LLM_PROVIDER`:

| Provider | Setting | Where documents go | Best for |
| --- | --- | --- | --- |
| **Claude** (default) | `RFP_LLM_PROVIDER=claude` + `ANTHROPIC_API_KEY` | Anthropic's API | Highest accuracy with no hardware to run |
| **Your own models** | `RFP_LLM_PROVIDER=openai_compatible` + `RFP_OPENAI_BASE_URL` + `RFP_OPENAI_MODEL` | Your server only | Companies that cannot send bid data to a cloud AI (defence, government contractors, strict client NDAs), or that already run models in-house |

The second option works with any server that speaks the OpenAI-compatible chat API: **Ollama, vLLM,
llama.cpp server, LM Studio**, or hosted endpoints. Both providers run the same prompts and output schemas
(`backend/app/llm.py`); only the transport differs (`backend/app/llm_openai.py`). Everything else (parsing,
search, citation checks, scoring, review, export) is identical.

Example with Ollama on the same machine:

```bash
ollama pull qwen3:32b                       # pick a model your hardware can run
OLLAMA_CONTEXT_LENGTH=32768 ollama serve    # long RFP sections need a long context

# backend/.env
RFP_LLM_PROVIDER=openai_compatible
RFP_OPENAI_BASE_URL=http://localhost:11434/v1
RFP_OPENAI_MODEL=qwen3:32b
RFP_DRAFT_WORKERS=1                         # one answer at a time on a single GPU
```

**Will it work the same?** The workflow does; accuracy depends on the model. To make smaller models
dependable, the adapter:

- asks the server to force output into the exact JSON schema (constrained decoding), and falls back to
  plain JSON mode or schema-in-the-prompt if the server does not support it;
- strips `<think>` reasoning that some models print before the answer;
- validates every reply and retries with the validation error, up to `RFP_OPENAI_RETRIES` times;
- refuses silently truncated prompts: Ollama cuts long input to the model's context length without an
  error, which would otherwise look like missed requirements. You get a clear error telling you to raise
  the context length or lower `RFP_EXTRACTION_WINDOW_CHARS`.

Citation verification is model-independent, so a weaker model's unsupported claims still land in the
review queue. But a model that misses requirements is a real risk, so **measure before you trust it**:

```bash
cd backend
../.venv/bin/python -m evals.extraction --provider openai_compatible --model qwen3:32b
```

This reports recall on the labelled test set (see [Measuring accuracy](#measuring-accuracy)) so you can
compare models, quantizations and context settings on your own hardware. Rough sizing: a model needs about
its parameter count in GB of GPU memory at 8-bit, or roughly half that at 4-bit, plus room for a long
context; models around 30B parameters and up are the realistic starting point for this kind of
extraction, and small (1-8B) models are best treated as a fallback until the eval says otherwise.

## Run it locally

Requirements: Python 3.12+, Node 20+, Postgres 15+.

**1. Database.** With Docker: `docker compose up -d` (creates the `rfp` role and the `rfp` and `rfp_test` databases).
Without Docker, install Postgres and run the statements in [`deploy/postgres-init.sql`](deploy/postgres-init.sql) as a superuser.
The app must connect as a regular role, not a superuser, or row-level security is bypassed (the API logs a warning if so).

**2. Backend** (http://localhost:8000, API docs at `/docs`):

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env        # set ANTHROPIC_API_KEY
cd backend
../.venv/bin/alembic upgrade head           # create tables and security policies
../.venv/bin/uvicorn app.main:app --reload
```

**3. Frontend** (http://localhost:3000), in a second terminal:

```bash
cd frontend
npm install
npm run dev        # proxies /api/* to the backend; set BACKEND_URL to change where
```

Open http://localhost:3000, create your company account, upload a few past proposals to the
library, then create a bid and upload a solicitation.

**Tests** use a fake AI model, so they need no API key, but they do need Postgres:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://rfp:rfp@localhost:5432/rfp_test "$PWD/../.venv/bin/python" -m pytest -q
```

The same checks run on GitHub Actions for every push ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Project layout

```
backend/
  app/
    main.py        API routes
    auth.py        sign-in, sessions, invites, roles
    db.py          engine, tenant-scoped sessions (row-level security binding)
    models.py      database tables
    parsing.py     file parsing, chunking, obligation sweep
    retrieval.py   Postgres full-text search
    llm.py         AI tasks, prompts, schemas, Claude provider
    llm_openai.py  self-hosted / OpenAI-compatible provider (Ollama, vLLM, llama.cpp, LM Studio)
    pipeline.py    background jobs: ingest, extract, addendum diff, draft, verify, score
    export.py      Word/Excel export, readiness check
  migrations/      Alembic migrations (schema + row-level security policies)
  evals/           requirement-extraction evaluation: labelled cases, scoring, reports
  tests/           API flow, auth, isolation, eval-harness and unit tests
frontend/
  app/             Next.js pages: bids, bid workspace, library, team, sign-in
  components/      shared UI and session handling
  lib/             API client and types
deploy/            Postgres init script
.github/workflows/ CI: tests on Postgres, migration check, frontend build, dependency audit
docker-compose.yml local Postgres
```

## Configuration

All backend settings are environment variables (or `backend/.env`); see
[`backend/.env.example`](backend/.env.example). The most important:

| Variable | Default | Purpose |
| --- | --- | --- |
| `RFP_LLM_PROVIDER` | `claude` | `claude` or `openai_compatible` (self-hosted / local models) |
| `ANTHROPIC_API_KEY` | none | Claude API key |
| `RFP_OPENAI_BASE_URL` / `RFP_OPENAI_MODEL` | `http://localhost:11434/v1` / none | Self-hosted model server and model name |
| `RFP_DATABASE_URL` | `postgresql+psycopg://rfp:rfp@localhost:5432/rfp` | App database connection (regular role) |
| `RFP_MODEL` / `RFP_EFFORT` | `claude-opus-5-5` / `high` | Model and reasoning effort |
| `RFP_REVIEW_THRESHOLD` | `0.6` | Answers below this confidence go to review |
| `RFP_ALLOW_SIGNUP` | `true` | Allow new companies to sign up |
| `RFP_COOKIE_SECURE` | `false` | Set `true` behind HTTPS |
| `RFP_FORWARDED_HOPS` | `0` | Number of reverse proxies (nginx, Caddy, a load balancer) in front of the app that append to `X-Forwarded-For`; set to `1` behind one so failed logins are also limited per visitor address. Keep the API port private when this is above 0 |
| `RFP_DRAFT_WORKERS` | `4` | Answers drafted in parallel; 1-2 for a single local GPU |
| `RFP_MAX_PDF_PAGES` / `RFP_MAX_SHEET_ROWS` / `RFP_MAX_UNZIPPED_MB` | `2000` / `100000` / `300` | Largest document the parser accepts |
| `FRONTEND_HTTPS` (frontend) | unset | Set `true` when the site is served over HTTPS to send HSTS |

## License

[MIT](LICENSE). Free to use, modify and build on.
