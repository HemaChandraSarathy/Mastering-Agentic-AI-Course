# Evaluation

Two golden sets, one per pipeline:
- **Pipeline A — extraction accuracy** (the numbers): `golden_extraction.py` + `run_extraction_eval.py` → `runs/extraction_report.md`.
- **Pipeline B — narrative RAG quality** (the "why"): `questions.py` + `run_eval.py` → `runs/report.md`.

## Pipeline A — extraction golden set

`golden_extraction.py` pins hand-authored expected `(metric_type, period, value)` rows for one
fixture per extraction engine, and `run_extraction_eval.py` scores the extractor against them
(exact-match recall / precision / provenance coverage). Truth is authored independently of the
extractor (sample-data generator literals / published filing figures) so the benchmark is not
circular; a negative-control test confirms the scorer flags corrupted values and missing metrics.

| Fixture | Engine | Expected | Recall | Precision | Provenance |
|---|---|--:|--:|--:|--:|
| Meridian financials | `excel` (openpyxl) | 52 | 1.00 | 1.00 | 100% |
| Atlas summary | `text_pdf` (pdfplumber tables) | 15 | 1.00 | 1.00 | 100% |
| ConocoPhillips Q3'25 10-Q | `image_pdf` (LiteParse OCR + reconstruct) | 24 | 1.00 | 1.00 | 100% |
| **Overall** | — | **91** | **1.000** | **1.000** | — |

Regenerate fixtures: `python eval/make_extraction_fixtures.py` · Run: `python eval/run_extraction_eval.py`.
Both are network-free and LLM-free — pure deterministic checks that gate against OCR / table-parse / mapping regressions.

## Pipeline B — narrative RAG

The course (Project 2) requires: **two chunking strategies compared**, a **reranking impact
analysis**, and a question set with **failure analysis** including refusal cases.

## Question set
`questions.py` — 15 questions across 4 categories:
- `single_doc` (4) · `cross_quarter` (3) · `cross_doc` (4) · `unanswerable` (4, must refuse)

## Harness (runs once keys are set)
1. **Chunking A/B** — index the corpus under `fixed` and `structural` strategies; run all
   answerable questions; compare retrieval quality (hit@k: does a chunk from the expected
   source/period appear in top-k).
2. **Reranking impact** — measure top-k before vs after an LLM/cross-encoder rerank.
3. **Faithfulness (RAGAS)** — generated answers grounded in retrieved context, target ≥90%.
4. **Refusal** — unanswerable questions must produce "not found in this company's documents."

Run today (no keys): `python scripts/run_retrieval.py` — BM25 sparse baseline.

## Final results (full hybrid + rerank + generation — see runs/report.md)

| Metric | Result |
|---|---|
| Chunking hit@3 — **fixed** | 4/4 |
| Chunking hit@3 — **structural** | 3/4 |
| Rerank impact (structural) | 3/4 (no change on this small set) |
| Faithfulness (LLM-judge, mean) | **1.00** (target ≥0.90) |
| Refusal accuracy (unanswerable) | **4/4** |

**Chunking takeaway:** fixed-size *edged* structure-aware here — structural chunking splits the
long Morgan Stanley report into many heading-scoped chunks, which lowered recall on the broad
"summarize the macro backdrop" query (Q10) vs. fixed's larger windows. So structure-aware isn't
universally better; it helps on precise/quoted lookups, fixed helps on broad synthesis. (Small
n=4 evaluable set — directional, not definitive.)

**Two test-design corrections found by running it:** (a) the faithfulness judge must *count
claims* (a bare-number judge under-scored fully-grounded answers, even returning 0.0); (b) "how
many employees" was mislabeled unanswerable — the ARGUS report lists headcount and the system
correctly answered it, so it was swapped for a genuinely out-of-range question.

## Earlier findings (sparse BM25 baseline, before embeddings)

**1. Sparse-only refusal does not work (0/4).** BM25 scores are uncalibrated and the
unanswerable questions (score ~5–6) overlap answerable ones (e.g. Q11 scored 4.4), so no
fixed threshold separates them. **Conclusion:** refusal belongs at the *generation* step —
the LLM is given only the retrieved context and instructed to refuse when the answer isn't
present — backed by dense-retrieval relevance, not a lexical score cutoff. (This is the
"design the refusal path first" lesson; the threshold is a weak prior, not the decision.)

**2. Lexical retrieval can't disambiguate period.** "Who hosted the **Q3 2025** call?"
returned the **Q4 2024** transcript — all four transcripts share the same participant
roster, so lexical overlap is near-identical. **Fix:** dense embeddings + metadata
filtering on `period` (we tag every chunk with company/doc_type/period for exactly this).

**3. Numbers must not come from retrieval.** Factual figure questions (Q1, Q4) surface the
narrative ARGUS report, not the exact quarterly figure — by design. Those answers come from
**Pipeline A** (deterministic + confirmed); narrative retrieval supplies the "why," not the
"what." This is the two-pipeline split working as intended.

**4. PDF hygiene matters.** The ARGUS report rendered every glyph 4× (`CCCCOOOO...`);
un-garbling it (collapse 3+ identical-char runs) was required before its tokens were usable.
