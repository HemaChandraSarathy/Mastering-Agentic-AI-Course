# LiteParse trial — image-only PDF extraction

**Date:** 2026-06-11 · **Package:** `liteparse==2.0.7` (cp314 wheel, native Rust, Apache-2.0)
**Fixture:** `_scratch/trial_boardpack.pdf` — a real income-statement page rendered to an
**image-only PDF** (no text layer), the shape of a scanned board pack. Figures are public
ConocoPhillips Q3'25 data used as a labeled ground-truth spot-check, not customer data.

## What this tests
Our current numbers path (`pipeline_a.extract_from_excel`) is **Excel-only**; our narrative
path uses **pdfplumber**, which reads the *text layer* of a PDF. On an image-only page there
is no text layer — so today an image PDF yields **zero** extractable content. This measures
that gap and whether LiteParse (local, bundled OCR) closes it.

## Result

| Extractor | Chars | Structured units | Time | Ground-truth figures found | Avg confidence |
|---|---|---|---|---|---|
| **pdfplumber** (current) | 0 | 0 tables | 2 ms | 0/4 | n/a |
| **LiteParse** (OCR) | 3208 | 164 text items | 2406 ms | 4/4 | 0.94 |

Ground-truth set: `['15,031', '13,041', '45,552', 'September 30']`.
pdfplumber found: `[]` · LiteParse found: `['15,031', '13,041', '45,552', 'September 30']`.

## Provenance upgrade
LiteParse returns per-token bounding boxes + OCR confidence. Locating the figure `15,031`
on the page:

- **bbox (x, y, width):** `(329.3, 200.6, 25.9)` on a `587.5 x 760.3` pt page
- **OCR confidence:** `0.967`

This is stronger than our current `tab!cell_ref` provenance (which only exists for Excel):
for a scanned page we now get an exact on-page coordinate + a confidence we can feed into the
transparency triad (source + recency + confidence).

## What worked / what to watch

**Worked**
- Installed clean on **Python 3.14** via a prebuilt `cp314` wheel — no Rust toolchain, no
  build-from-source (unlike torch, which has no 3.14 wheels).
- **OCR ran with no system Tesseract on PATH** — the engine is bundled. Removes the external
  dependency I expected to have to install.
- **Local, no API key, no cloud** — financials never leave the machine (the PE-buyer security
  objection that hosted LlamaParse carried does not apply here).
- Deterministic (no LLM in the parse) — fits Pipeline A's integrity story.
- Extracted the real table figures off an image page where pdfplumber got **0 chars**.

**To watch**
- Output is **text + positioned tokens**, not reconstructed table cells. To feed Pipeline A
  we still need a row/column reconstruction step (group tokens by y -> rows, by x -> columns)
  before taxonomy mapping. LiteParse gives the coordinates to do this; it does not hand back a
  clean grid. LlamaParse (cloud, LLM) reconstructs tables more directly — the tradeoff.
- `search_items()` helper rejects the public `TextItem` type (wants the native `PyTextItem`);
  phrase-location was done with a manual scan instead. Minor API wrinkle.
- This is one clean page. Validate on a genuinely messy multi-column / merged-cell board pack
  before committing — that's where OCR table reconstruction gets hard.

## Where it slots in
Behind the existing `file -> {line items + provenance}` seam, as one implementation of the
extraction layer — swappable with pdfplumber (text PDFs) and openpyxl (Excel). Adopt it for
the **image-only PDF path**, add a token-grouping step to rebuild table rows, then map through
the taxonomy and run the same validate/reconcile/variance downstream unchanged.

---

# Part 2 — End-to-end through Pipeline A

The token-grouping step is built: `pipeline_a/reconstruct.py` turns LiteParse's positioned
tokens into rows/columns (cluster by y; infer period columns from the stacked header;
snap numerics to the nearest column anchor; map label -> taxonomy). An image-only PDF now
flows through the **same** validate -> variance downstream as a messy Excel.

| Stage | Current (pdfplumber) | LiteParse + reconstruct |
|---|---|---|
| Values off the image page | 0 | 90 (24 mapped to taxonomy, 66 unmapped & surfaced) |
| Quarter columns recovered | — | ['Q3 2024', 'Q3 2025'] |
| YTD columns (kept, excluded from QoQ) | — | ['9M 2024', '9M 2025'] |
| Validation flags | — | 0 (0 error) |

**Validation — reconciliation held on the OCR'd numbers.** With 0 flags and
0 errors, the income-statement identities pass on the OCR output itself:

- `income_before_taxes == total_revenues - total_costs`
- `net_income == income_before_taxes - income_tax`

i.e. OCR was accurate enough that the numbers are internally consistent — the reconciliation
check doubles as an OCR-quality gate (a mis-read digit would break the identity and flag).

**Variance** (QoQ machinery over quarter columns; this single 10-Q page yields a Q3'24->Q3'25
*YoY* pair, not a Q2->Q3 sequence):

| Metric | Period | Value | Prior | Change | Flagged |
|---|---|---:|---:|---:|:--:|
| revenue | Q3 2025 | 15,031 | 13,041 | +15.3% | yes |
| total_revenues | Q3 2025 | 15,522 | 13,604 | +14.1% | yes |
| total_costs_and_expenses | Q3 2025 | 12,594 | 10,369 | +21.5% | yes |
| income_before_income_taxes | Q3 2025 | 2,928 | 3,235 | -9.5% |  |
| income_tax_expense | Q3 2025 | 1,202 | 1,176 | +2.2% |  |
| net_income | Q3 2025 | 1,726 | 2,059 | -16.2% | yes |

**What this proves:** the only thing that changed vs the Excel path is the *extractor*. Taxonomy
mapping, reconciliation, and variance are byte-for-byte the existing code. So adopting LiteParse
for image PDFs is additive — a new entry behind the `file -> {line items + provenance}` seam —
not a rewrite. Repro: `scripts/image_pdf_pipeline_demo.py` (console) / `scripts/liteparse_trial.py` (this doc).

**Still to validate before production:** a genuinely messy board pack (merged cells, multi-table
pages, rotated scans) — this fixture is a clean single-table page. The reconstruction is geometric
(y-clustering + x-snapping); pages with overlapping tables or non-aligned columns will need the
grouping heuristics hardened, and any reconciliation break should hard-stop to the confirm gate.

---

# Part 3 — Wired into ingest routing

`ingest.py` now routes by file *content*, not just extension. An image-only PDF used to be
detected and **skipped** (`image_pdfs_skipped`); it now runs through **one LiteParse OCR pass
that feeds both pipelines**:

| Input | Route |
|---|---|
| `.xlsx` / `.xls` | Pipeline A numbers → `rag_metrics` |
| `.pdf` *with* a text layer | **BOTH:** pdfplumber tables → Pipeline A numbers **+** page text → Pipeline B narrative |
| `.pdf` image-only | **LiteParse OCR once →** tokens→reconstruct→Pipeline A numbers **+** page-text→Pipeline B narrative |
| `.txt` / `.md` | Pipeline B narrative → `rag_chunks` |

Numbers always come from a deterministic path — Excel cells, **pdfplumber table cells**, or OCR
token reconstruction — never from narrative RAG. A text PDF's *tables* go to Pipeline A even
though its *prose* goes to Pipeline B (non-financial tables, e.g. a transcript layout, yield
nothing since they have no period header). Shared engine: `extract.metrics_from_grid`.

Routing rationale: a board pack carries tables *and* commentary on the same scanned pages, so an
image PDF feeds **both** numbers and narrative off a single OCR pass (no double-parse). Validation
and variance run **once over the combined** Excel + image-PDF metric set, so periods reconcile
across sources; YTD (`9M`) columns are stored but excluded from QoQ.

Offline routing check (network stubbed) on `trial_boardpack.pdf` + a `.txt` transcript:
`metrics_stored=24` (image PDF, incl. variance + OCR confidence + bbox provenance),
`chunks` from both the OCR'd PDF and the transcript, `image_pdfs_ocred=['trial_boardpack.pdf']`.
The image PDF is no longer skipped — it contributes to **both** stores.

---

# Part 4 — Robustness (deskew) + extraction golden set

A deliberately messy fixture (two tables on one page, a merged group header, a **1.5° scan
skew**) initially extracted **0 metrics**: skew desynchronizes each row's label from its values,
so no row has both. Added a **projection-profile deskew** (`reconstruct._estimate_skew_deg`):
estimate the page tilt from token baselines, cluster rows on de-rotated y. It recovered the
page **0 → 8/10** — and crucially **never guesses label↔value pairing** (that would risk a wrong
number); it only corrects geometry. The remaining 2 misses are an OCR character error
("Cash"→"Gash") that safely fails to map rather than mis-mapping.

The numbers side now has its own golden benchmark — `eval/golden_extraction.py` +
`eval/run_extraction_eval.py` → `eval/runs/extraction_report.md`, one fixture per engine, scored
against hand-authored truth (negative-control verified — it can fail):

| Fixture | Engine | Recall | Precision | Provenance |
|---|---|--:|--:|--:|
| Meridian financials | excel | 1.00 | 1.00 | 100% |
| Atlas summary | text_pdf (pdfplumber tables) | 1.00 | 1.00 | 100% |
| ConocoPhillips 10-Q | image_pdf (OCR) | 1.00 | 1.00 | 100% |
| Vesper (messy: 2 tables, skew) | image_pdf (OCR) | **0.80** | **1.00** | 100% |

**Precision holds at 1.00 on the messy page** — the pipeline **misses rather than fabricates**,
the correct failure mode for financial numbers. Clean fixtures stayed 1.00 (deskew is a no-op on
straight pages). Overall: 99/101 exact across 4 fixtures.
