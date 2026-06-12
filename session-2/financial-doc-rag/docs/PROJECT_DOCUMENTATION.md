# Financial Document Intelligence Pipeline — Project Documentation

**Gen Academy · Mastering Agentic AI — Week 2 RAG Project**
**Build track:** Track 2 (LangChain + LangGraph, Python)
**Repository:** `session-2/financial-doc-rag` · **Demo:** Streamlit (`streamlit run app.py`)

---

## Project overview

This project turns a portfolio company's **document folder** (financial statements, earnings
transcripts, analyst reports, news) into a **first-draft, analyst-confirmed insights one-pager** in
under ten minutes, where **every figure and claim cites its source**.

The defining design decision is that it is **not one RAG app — it is two pipelines**:

- **Pipeline A — numbers — is deterministic, NOT RAG.** Financial figures are parsed straight from
  tables (Excel cells, text-PDF tables, or OCR'd image-PDF tables), mapped to a canonical metric
  taxonomy, validated against reconciliation identities, and compared period-over-period. **No
  embedding or similarity search ever touches a number** — a reported mark must never come from a
  vector lookup.
- **Pipeline B — narrative — is RAG.** Transcripts, analyst reports and news are chunked, embedded,
  retrieved (hybrid dense + sparse, reranked, period-filtered), and used to generate the cited "why,"
  with a refusal path when the answer isn't in the corpus.

A **human review & confirm gate** sits between extraction and the one-pager: the analyst confirms or
edits every figure before it flows into the brief. The whole thing is orchestrated as a **LangGraph**
state machine and traced in **LangSmith**.

The headline insight, validated by our own evaluation: the failure mode that classic financial-RAG
tutorials spend the whole project fixing — a number retrieved from the wrong chunk — is *structurally
impossible* in this design, because numbers never enter the RAG path.

---

# Part 1 — RAG Framework

This is the course "RAG framework" applied to **Pipeline B**, the graded RAG core (the narrative
"why"). Pipeline A is covered in Part 3 / Architecture because it is deliberately *not* RAG.

| Field | Decision |
|---|---|
| **Use case** | "What changed this quarter, and why?" for a PE deal-team analyst — surfaced as a cited insights one-pager plus a standalone Q&A box. |
| **Corpus** | One portfolio company's folder (~3–10 docs/quarter). **Narrative corpus (RAG):** earnings-call transcripts, analyst reports, news releases. **Numeric corpus (deterministic, not RAG):** quarterly financial statements (Excel + PDF). |
| **Ingestion & cleaning** | Per-type loaders. Text PDFs via `pdfplumber`; image-only PDFs via **LiteParse OCR** (local, no keys); plain text directly. Cleaning strips repeated headers/footers, page numbers, and watermark artifacts (one report rendered every glyph 4×, e.g. `CCCCOOOO…` → collapse runs of identical chars). Every chunk is tagged `{company, doc_type, period, source_file, page}`. |
| **Ingestion & freshness** | Batch on folder drop (no live feed). Incremental: new files can be added without re-ingesting the corpus. The "latest period" tag drives variance; the one-pager regenerates on demand. |
| **Chunking & embedding** | **Three strategies compared:** (A) fixed-size (~1000 tokens / 150 overlap), (B) structure-aware (split on sections/speaker turns), (C) **embedding-based semantic** (sentence-distance breakpoints at a cosine-distance percentile). Embeddings via **Nebius Token Factory** (Qwen3-Embedding-8B), truncated to **1024-dim** (Matryoshka) to fit the pgvector HNSW index. |
| **Retrieval strategy** | **Hybrid** = dense (pgvector cosine) + sparse (BM25), fused with **Reciprocal Rank Fusion**, then **period metadata filtering** (so "Q3 2025" doesn't return the Q2 transcript), then a **cross-encoder rerank** (FlashRank, `ms-marco-MiniLM-L-12-v2`). top-k ≈ 8 → rerank → top-4. **Refusal path designed first:** below-threshold relevance → "Not found in this company's documents," never a hallucinated answer. |

---

# Part 2 — Build Track

**Track 2 — LangChain + LangGraph (Python).**

| Choice | Why |
|---|---|
| **LangGraph** (over a linear chain) | The flow has two parallel pipelines that converge at a **human-in-the-loop confirm gate**. LangGraph's `StateGraph` + `interrupt()` model that natively: the graph holds state (raw docs, extracted metrics, validation flags, variance, retrieved chunks, confirm status), pauses for the analyst, then resumes. A plain chain can't express the gate. |
| **LangChain** | Loader/splitter/retriever primitives and the embeddings/LLM client abstractions — kept behind our own interfaces so vendors stay swappable. |
| **Python** | The deterministic numeric path needs `pdfplumber` / `pandas` / `openpyxl` and an OCR parser — all Python. (Tradeoff: a production port to a Deno/TS stack would run extraction as a small Python microservice behind a clean `file → {line items + provenance}` interface.) |
| **Supabase pgvector** | One Postgres holds **both** the narrative vectors **and** the structured metrics — vectors and numbers live together, one fewer vendor than a dedicated vector DB. |
| **Nebius Token Factory** | Course requirement to route ≥1 model call through Nebius; we use it for the **embedding** call. Generation uses Anthropic `claude-sonnet-4-6`. |
| **LiteParse** (LlamaIndex, Apache-2.0) | Local, Rust-based, **bundled OCR — no cloud, no API key**, so financials never leave the machine. Chosen over hosted parsers (data-egress / security) and over a pure-vision LLM parse (non-deterministic). |
| **Streamlit** | Fast demo UI that renders the same `CompanyInsightData` one-pager shape the production view would, styled with a custom editorial design system. |

---

# Part 3 — Use case: portfolio-company document ingestion → insights platform

**Who:** a private-equity deal-team analyst responsible for several portfolio companies.

**The pain (validated, not assumed):** the time sink in portfolio reporting isn't writing the report —
it's **everything before** the report. Each quarter the analyst re-keys figures out of PDFs,
normalizes inconsistent Excel tabs, reconciles definitions, checks them against last quarter, and only
then hand-builds a one-pager. The numbers are scattered across formats; the "why" is buried in
transcripts and analyst notes.

**What the product does:** drop the quarter's document folder and get back a structured **insights
one-pager** — key metrics with QoQ variance and flags, data-source coverage, and a cited narrative
summary (headwinds / tailwinds / sentiment) — that the analyst **reviews and confirms** rather than
builds from scratch. Provenance is on every value (source cell or OCR bounding box) and every claim
(retrieved chunk + page).

**Why two pipelines for this use case specifically:** in PE, **every number carries decision weight.**
A fabricated EBITDA margin or a leverage ratio pulled from the wrong chunk can corrupt a mark or
misframe an investment-committee discussion. So numbers are extracted deterministically and
reconciled; only the narrative — where paraphrase is acceptable and citations make it auditable — uses
RAG. The output schema (`CompanyInsightData`) maps 1:1 to a portfolio insights view: `metrics[]` with
QoQ/flag, `dataSources[]` + `dataQuality` for coverage, and `summary`/`sentiment`/`headwinds`/
`tailwinds` for the narrative. The one judgment field (`recommendations[]`) is intentionally left
empty — the product **aggregates and attributes; it does not editorialize**.

---

## Architecture

```
                       ┌──────────  corpus folder drop  ──────────┐
                       ▼                                           ▼
   PIPELINE A — DETERMINISTIC NUMBERS (no embeddings)     PIPELINE B — NARRATIVE RAG
   ─────────────────────────────────────────────         ──────────────────────────────
   Excel  → openpyxl cells                                transcripts / analyst / news
   text PDF → pdfplumber tables          ┐                 → clean (+ OCR for image text)
   image PDF → LiteParse OCR + deskew     │ shared          → chunk (fixed | structural | semantic)
                → token→row/column grid   ┘ grid engine     → embed (Nebius, 1024-dim)
        │                                                   → upsert to pgvector + BM25 index
        ▼  map raw label → canonical taxonomy (38 + 6)            │
        ▼  validate (range / comparison / RECONCILIATION)         │  retrieve: hybrid (dense+BM25)
        ▼  variance (QoQ vs prior quarter, ≥10% flag)             │           → RRF → period filter
        │                                                         │           → FlashRank rerank
        │                                                         │           → refusal-first generate
   ╔════╧═════════════════════════════════╗                       │
   ║   HUMAN REVIEW & CONFIRM GATE         ║ ← analyst confirms / edits each figure
   ╚════╤═════════════════════════════════╝                       │
        │ (confirmed numbers + variance)        (cited narrative passages)
        └───────────────────────┬───────────────────────────────────┘
                                ▼
              Assemble insights one-pager  (CompanyInsightData, fully cited)
              numbers → metrics[] / dataSources[] / dataQuality
              narrative → summary / sentiment / headwinds / tailwinds
              recommendations[] → empty (aggregation, not editorial)
```

LangGraph holds the state and routes both pipelines into the one-pager; LangSmith traces every node.

### Architecture logic — why each piece exists

- **Deterministic numbers.** Table parse → taxonomy map → validate → variance. Reproducible: the same
  document always yields the same numbers. No model is in the loop, so there is nothing to hallucinate.
- **Reconciliation as a correctness gate.** The validator enforces income-statement identities —
  `income_before_taxes = total_revenues − total_costs` and `net_income = income_before_taxes −
  income_tax`. When these hold on extracted (even OCR'd) values, it is strong evidence the digits are
  right; a break hard-stops the page to the confirm gate instead of shipping a wrong number.
- **Shared grid engine.** Excel, text-PDF tables, and OCR-reconstructed tables all emit the **same**
  `ExtractedMetric` and flow through identical validate/variance/one-pager code. Adding a new input
  format = adding an extractor behind one seam, not a rewrite.
- **Confirm gate.** Encodes the product rule "review and confirm, never trust an unconfirmed number."
  It is also the ground-truth step — the analyst spot-verifies against the filing.
- **RAG only for narrative.** Paraphrase is acceptable for the "why"; citations make it auditable;
  refusal prevents fabrication.

---

## Workflow — step by step

1. **Folder drop / ingest.** Files are routed by *content*, not just extension:
   - `.xlsx/.xls` → Pipeline A numbers.
   - `.pdf` with a text layer → **both**: `pdfplumber` tables → Pipeline A; prose → Pipeline B.
   - `.pdf` image-only → **one LiteParse OCR pass → both**: positioned tokens → reconstruct → Pipeline
     A numbers; page text → Pipeline B narrative.
   - `.txt/.md` → Pipeline B narrative.
2. **Extract numbers (Pipeline A).** Parse tables → map each row label to the canonical taxonomy
   (unmapped labels are surfaced, never force-fit) → emit `ExtractedMetric` rows with provenance
   (cell ref or OCR bounding box) and confidence.
3. **Validate.** Range rules (e.g. margin ≤ 100%), comparison rules (net ≤ pretax), and reconciliation
   identities. Violations are flagged, not silently dropped.
4. **Variance.** QoQ deltas vs the prior quarter per metric; ≥10% surfaces a flag.
5. **Embed & index narrative (Pipeline B).** Clean → chunk → embed (Nebius) → upsert to pgvector +
   build BM25 index, all tagged with `period` / `doc_type` / `source_file`.
6. **Human confirm gate.** The analyst reviews extracted metrics + flags + variance beside the source
   reference and confirms or edits. Only confirmed values continue.
7. **Retrieve & generate (Pipeline B).** Hybrid retrieve → RRF → period filter → rerank →
   refusal-first generation of the cited narrative.
8. **Assemble the one-pager.** Confirmed numbers → `metrics[]` / `dataSources[]` / `dataQuality`;
   cited narrative → `summary` / `sentiment` / `headwinds` / `tailwinds`. Rendered in Streamlit.

---

## Tools used

| Layer | Tool | Role |
|---|---|---|
| Orchestration | **LangGraph** | State machine + human-in-the-loop confirm gate |
| Framework | **LangChain** | Loaders, splitters, retriever/LLM abstractions |
| Tracing | **LangSmith** | Trace every node and eval run |
| Embeddings | **Nebius Token Factory** — Qwen3-Embedding-8B | Dense vectors, 1024-dim (Matryoshka truncation) |
| Generation & LLM-judge | **Anthropic `claude-sonnet-4-6`** | Cited narrative + RAGAS-style eval judging |
| Vector + structured store | **Supabase Postgres + pgvector** | `vector(1024)` HNSW, `tsvector` BM25, structured metric rows |
| Numeric extraction | **pdfplumber, pandas, openpyxl** | Excel cells + text-PDF tables (deterministic) |
| OCR extraction | **LiteParse** (Rust, bundled OCR, Apache-2.0) | Image-only PDFs, local, no keys |
| Sparse retrieval | **rank-bm25** | Lexical signal in the hybrid retriever |
| Reranking | **FlashRank** (`ms-marco-MiniLM-L-12-v2`, ONNX) | Cross-encoder rerank; calibrated scores for refusal |
| UI | **Streamlit** | Demo one-pager + ingest canvas + Q&A |
| Reliability | DNS-over-HTTPS host pinning | Robust Supabase connectivity on flaky networks |

---

## Extraction engines (Pipeline A in detail)

Three deterministic engines feed the same downstream:

1. **Excel (`openpyxl`).** For each sheet, find the header row (first row with ≥2 parseable period
   tokens), infer the label column, and emit one metric per (row × period). Handles messy banner/title/
   note rows without hardcoded offsets.
2. **Text-PDF tables (`pdfplumber`).** `extract_tables()` per page → the same grid engine. Non-financial
   tables (e.g. a transcript's layout) simply produce nothing — no period header, no metrics.
3. **Image-only PDF (LiteParse OCR → geometric reconstruction).** OCR yields positioned tokens, not a
   grid. We reconstruct the table with **geometry, not ML**: cluster tokens into rows by y; detect
   period columns from the (possibly stacked, merged) header; infer each column's period (e.g. "Three
   Months Ended September 30, 2025" → `Q3 2025`); snap numeric tokens to the nearest column anchor.
   A **projection-profile deskew** corrects crooked scans by estimating page tilt from token baselines
   and clustering rows on de-rotated y — crucially it only fixes geometry and **never guesses which
   label owns which value** (that would risk a wrong number).

All three emit `ExtractedMetric` with provenance + confidence and run through the identical
validate → variance → one-pager path.

---

## Retrieval strategies (Pipeline B in detail)

- **Chunking — three strategies compared.** Fixed-size, structure-aware, and embedding-based semantic.
  Each indexed and evaluated (results below).
- **Hybrid retrieval.** Dense (pgvector cosine) + sparse (BM25), fused with **Reciprocal Rank Fusion**
  so neither signal dominates.
- **Period metadata filtering.** Every chunk carries its `period`; a query for "Q3 2025" filters out
  same-roster transcripts from other quarters that lexical/dense overlap would otherwise surface. (We
  found lexical retrieval alone returned the wrong quarter precisely because all transcripts share the
  same participant list.)
- **Cross-encoder rerank.** FlashRank reorders the fused candidates; its calibrated scores double as a
  refusal signal.
- **Refusal-first generation.** The model receives only the retrieved context and is instructed to
  refuse — "Not found in this company's documents" — when the answer isn't present. Refusal is anchored
  at the generation step (backed by relevance), not a brittle lexical score cutoff.

---

## Datasets used

| Dataset | What | Why / integrity note |
|---|---|---|
| **Fictional sample companies** (Meridian — industrials; Cobalt — SaaS; Harbor — logistics) | Multi-tab messy Excel financials + earnings transcripts + analyst reports | **Authored for this project and clearly labeled FICTIONAL.** Because we wrote the numbers, they double as ground truth for the extraction eval. |
| **ConocoPhillips public SEC filing (Q3'25 10-Q income statement)** | A real income-statement page, rendered to an **image-only PDF** | A **labeled public-company placeholder** for a private portco's scanned board pack — used only because private data is unavailable. **Not customer data.** Its real, published figures are an independent ground truth for the OCR engine. |
| **Eval fixtures** | `text_financials.pdf` (text-layer table), `image_boardpack.pdf` (clean scan), `messy_boardpack.pdf` (two tables, merged header, 1.5° skew) | Reproducible fixtures, one per extraction engine, regenerable via a generator script. |

> Integrity rule observed throughout: no invented financial figure is ever presented as if it were
> real data. Synthetic data is labeled synthetic; the public placeholder is labeled a placeholder.

---

## Evaluation

Two golden sets — one per pipeline — because retrieval quality and extraction accuracy are different
risks.

### A) Pipeline B — narrative RAG quality
13 ground-truth questions (10 answerable with verified reference answers + relevant source substrings,
3 unanswerable for the refusal path). Metrics are LLM-judge approximations of RAGAS faithfulness /
context precision / context recall (the `ragas` package is skipped to avoid a Python-3.14 dependency
conflict; the judge counts claims and scores per-chunk relevance rank-aware).

### B) Pipeline A — extraction accuracy (built this iteration)
One fixture per extraction engine, scored against **hand-authored truth that is independent of the
extractor** (sample-data generator literals / published filing figures) — so the benchmark is not
circular. A **negative-control test** confirms the scorer actually fails when fed a corrupted value or
a missing metric (otherwise a perfect score would be meaningless).

---

## Results

### Narrative RAG (chunking A/B/C, config-level)

| Metric | A: Fixed (no rerank) | B: Semantic (no rerank) | C: Semantic + Rerank |
|---|---|---|---|
| Faithfulness | 1.000 | 0.700 | 0.586 |
| Context Precision | 0.292 | **0.633** | 0.583 |
| Context Recall | 0.817 | 0.600 | 0.550 |
| Refusal accuracy | — | — | **3/3** |

- **Semantic chunking lifts precision 0.29 → 0.63** vs fixed-size — keeping related sentences together
  yields cleaner context. Fixed-size keeps the highest recall (0.82) but the lowest precision (0.29):
  it grabs the right snippet *plus* noise, yet still answers faithfully (1.00).
- **Reranking was roughly neutral here (0.63 → 0.58)** — on a small, already-clean candidate set,
  trimming top-6 → top-3 occasionally drops a relevant chunk. Rerank value scales with corpus size and
  noise; its calibrated scores still help the refusal decision.
- The dramatic chunking gap that financial-RAG tutorials show (e.g. 0.00 → 0.95 on a 10-K) does **not**
  reproduce here — because **tables never hit RAG** in our design. The failure those projects spend
  all their effort fixing is the one our two-pipeline architecture avoids by construction.

### Extraction accuracy (Pipeline A golden set)

| Fixture | Engine | Expected | Recall | Precision | Provenance |
|---|---|--:|--:|--:|--:|
| Meridian financials | `excel` | 52 | 1.00 | 1.00 | 100% |
| Atlas summary | `text_pdf` (pdfplumber tables) | 15 | 1.00 | 1.00 | 100% |
| ConocoPhillips Q3'25 10-Q | `image_pdf` (LiteParse OCR) | 24 | 1.00 | 1.00 | 100% |
| Vesper board pack (messy: 2 tables, merged header, 1.5° skew) | `image_pdf` (OCR) | 10 | **0.80** | **1.00** | 100% |
| **Overall** | — | **101** | **0.980** | **1.000** | — |

- Clean fixtures: **100% recall and precision** across all three engines.
- The deliberately messy scan: **0.80 recall but precision stays 1.00** — the two misses are an OCR
  character error ("Cash" → "Gash") that **fails to map rather than mis-mapping**. The pipeline **misses
  rather than fabricates**, which is the correct failure mode for financial numbers.
- The income-statement **reconciliation identities held on the OCR'd numbers** — independent evidence
  the OCR digits were read correctly.

---

## Prompts used during vibe coding

Representative prompts that drove the build (generalized). The pattern was: state the architectural
principle, then iterate on fidelity and honesty.

**Architecture / principle:**
- "For the numbers, make it deterministic — not RAG. A mark must never come from a vector search."
- "Two pipelines: deterministic numbers + narrative RAG, with a human confirm gate between them."
- "Keep extraction behind a clean `file → {line items + provenance}` interface so the parser is swappable."

**Retrieval / RAG core:**
- "Keyword search alone isn't enough — make it hybrid (dense + sparse), fuse, then rerank. Measure the lift."
- "Design the refusal path first — if retrieval is weak, say 'not found,' never hallucinate."
- "Compare two chunking strategies and add a true semantic chunker; show the numbers."

**Honesty / evaluation:**
- "Compare our build against the course solution kit — tell me, honestly, where we're worse and what to improve."
- "Don't fabricate any financial figure — label synthetic data synthetic and the public sample as a placeholder."
- "Build an extraction golden set — and make sure the scorer can actually fail (negative control)."

**New capabilities this iteration:**
- "Learnt about LlamaIndex — can we use LiteParse for parsing? No cloud, no keys. Pros/cons."
- "Test-install LiteParse, wire an image-PDF trial, and compare outputs before vs after — document what worked."
- "Group the OCR tokens into rows/columns and run them through the existing taxonomy → validate → variance path."
- "Wire the ingest routing so an image PDF feeds both pipelines off one OCR pass."
- "Add deterministic table extraction for text PDFs too."
- "Add a deliberately messy fixture (two tables, merged header, skew) and document where it breaks."

**UI / product fidelity:**
- "Make the one-pager faithfully match the target insights layout — copy the spec, don't approximate."
- "Make the ingest tab look like the canvas/drop-zone view; remove the inner scroll, keep page scroll."
- "De-brand the sample to a fictional company; the app should just say 'upload files.'"

---

## Iterations tried (and what each taught)

1. **Chunking: fixed → structural → semantic.** First structural over-merged into a few coarse chunks
   and *lost* to fixed-size; switching to a true embedding-based semantic chunker lifted precision
   0.29 → 0.63. *Lesson: structure-aware isn't automatically better; measure it.*
2. **Sparse-only refusal (BM25).** Failed (0/4) — uncalibrated scores overlap answerable/unanswerable.
   *Moved refusal to the generation step, backed by dense relevance.*
3. **Period disambiguation.** Lexical retrieval returned the wrong quarter (shared transcript rosters).
   *Added `period` metadata tags + filtering.*
4. **Image-only PDFs.** pdfplumber returned 0 characters on scanned pages. *Added LiteParse OCR +
   geometric token→grid reconstruction.* First pass mis-labeled the second sub-column under a merged
   header (`FY 2024` instead of `Q3 2024`); fixed by inferring header context from the nearest token at
   or to the left.
5. **Messy/skewed scan → 0 metrics.** A 1.5° skew desynchronized labels from values. *Added a
   projection-profile deskew: 0 → 8/10, with precision held at 1.00 (misses, never fabricates).*
6. **Text-PDF tables.** A text PDF with a financial table had its numbers going only to narrative RAG.
   *Added deterministic `pdfplumber` table extraction sharing the Excel grid engine; routed text PDFs
   to both pipelines.*
7. **Evaluation rigor.** Early faithfulness judge under-scored fully-grounded answers (it counted bare
   numbers, not claims); a question was mislabeled "unanswerable" when the corpus actually contained
   it. *Fixed the judge and the labels by running the eval and reading failures.*
8. **Extraction benchmark.** Built a golden set with authored (non-circular) truth, then *negative-
   control-tested the scorer* so a perfect score is meaningful.

---

## Learnings & observations

- **Don't use RAG for the numbers.** Deterministic extraction + reconciliation eliminates an entire
  class of high-stakes failures; RAG is reserved for narrative, where citations make paraphrase safe.
- **Reconciliation is a free correctness gate.** Income-statement identities holding on extracted
  values (even OCR'd ones) is strong evidence they're right; a break should route to a human.
- **Provenance + refusal are non-negotiable for trust.** Every number shows its source; every claim
  cites a chunk; "not found" is a valid, preferred answer.
- **A benchmark must be able to fail.** Authored (non-circular) ground truth + a negative control are
  what make a "100%" meaningful. The extraction golden caught a real OCR miss the clean fixtures hid.
- **The right failure mode is "miss, don't fabricate."** On the messy scan, precision stayed 1.00 —
  the pipeline declined to emit the values it couldn't read rather than guessing.
- **Chunking matters, rerank scales with corpus.** Semantic chunking helped immediately; reranking was
  neutral at small scale but improves as candidate pools grow.
- **Image PDFs are solvable locally.** A local, open-source OCR parser (no cloud, no keys) reads board-
  pack scans and clears the data-security bar that hosted parsers don't.
- **One seam, many engines.** Excel, text-PDF, and OCR extraction all emit the same record and reuse
  the same validate/variance/one-pager code — new formats are additive, not rewrites.

---

## How to run / reproduce

```bash
python -m venv .venv && . .venv/Scripts/activate     # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                                  # add NEBIUS_API_KEY, ANTHROPIC_API_KEY,
                                                      # SUPABASE_URL, SUPABASE_SERVICE_KEY, (LANGSMITH_API_KEY)
streamlit run app.py                                  # → http://localhost:8501
```

Reproduce the evaluations (no UI needed):

```bash
python eval/make_extraction_fixtures.py     # regenerate the 3 extraction fixtures
python eval/run_extraction_eval.py          # → eval/runs/extraction_report.md   (extraction accuracy)
python eval/run_eval.py                      # → eval/runs/report.md              (narrative RAG A/B/C)
python scripts/liteparse_trial.py            # → docs/LITEPARSE_TRIAL.md          (OCR trial, 4 parts)
```

---

*Companion documents in `docs/`: `PROJECT_DOC.md` (concise overview), `IMPROVEMENTS.md` (before/after
table), `LITEPARSE_TRIAL.md` (the image/text-PDF extraction + deskew + golden trial in full).*
