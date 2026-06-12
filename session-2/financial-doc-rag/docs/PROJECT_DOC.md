# Financial-Doc-RAG — Financial Document Intelligence Pipeline
### Project Documentation (Gen Academy Week 2)

> **Data note.** Demonstrated on a **fictional** sample company, *Meridian Industrial Components*
> — all figures and narrative are fabricated and labeled as such. The earlier development corpus
> used ConocoPhillips public SEC data as a labeled placeholder. No real customer data is used.

---

## 1. What we built

A **two-pipeline** financial document intelligence system for a PE portfolio company. You drop a
company's document folder; the system produces a **cited, analyst-confirmed Insights one-pager** plus
grounded Q&A. The defining design choice — and the reason it differs from a textbook RAG project — is
that **financial numbers are NOT answered with RAG**:

- **Pipeline A — Numbers (deterministic).** Table extraction → map to a canonical metric taxonomy →
  validation/reconciliation → period-over-period variance. Exact, traceable to the source cell,
  self-checked. *No embeddings touch the numbers.*
- **Pipeline B — Narrative (RAG).** Chunk → embed (Nebius) → hybrid retrieve over Supabase pgvector →
  cross-encoder rerank (FlashRank) → cited generation (Claude) with a refusal path.
- A **human confirm gate** sits between extraction and the one-pager (review/edit, never a blank form).
- Orchestrated as a **LangGraph** state machine; persisted in **Supabase pgvector**; surfaced in a
  **Streamlit** UI styled to a custom design system.

**Why this matters:** the course's reference project spends its entire length proving that naive RAG
fails on financial *tables* (fixed-size chunking scores **0.00** context precision because rows and
headers split apart). Our architecture **avoids that failure mode entirely** by routing numbers through
deterministic extraction and reserving RAG for the qualitative "why." See `scripts/run_numbers_demo.py`.

---

## 2. Architecture

```
                         corpus folder (xlsx / pdf / txt)
                                      │
                 ┌────────────────────┴─────────────────────┐
                 ▼                                           ▼
   PIPELINE A — NUMBERS (deterministic)        PIPELINE B — NARRATIVE (RAG)
   pdfplumber / pandas table extract           load → chunk (fixed | structural | semantic)
        → map to taxonomy                       → embed (Nebius Qwen3-Embedding, 1024-d)
        → validate (range/compare/reconcile)    → Supabase pgvector  (hybrid: dense + BM25 + RRF
        → variance (QoQ)                           + period filter)
                 │                               → FlashRank cross-encoder rerank
                 ▼                                          │
        ╔═══════════════════════╗                          │
        ║ HUMAN REVIEW & CONFIRM ║   ← analyst confirms/edits; reconciliation re-runs
        ╚═══════════════════════╝                          │
                 │ confirmed metrics + variance             │ cited passages (Claude, refusal-first)
                 └───────────────────┬──────────────────────┘
                                     ▼
                 assemble Insights one-pager (CompanyInsightData) — cited
```

Orchestration: **LangGraph** (`graph.py`) with an `interrupt` confirm gate. Tracing: **LangSmith**.

---

## 3. Component reference

| Component | File | Type | LLM calls | Role |
|---|---|---|---|---|
| Ingest router | `ingest.py` | Pure Python | 0 | Routes xlsx → Pipeline A, pdf/txt → Pipeline B; persists; idempotent/incremental |
| Table extractor | `pipeline_a/extract.py` | pdfplumber / openpyxl | 0 | Structured line-item extraction with cell provenance |
| Metric taxonomy | `taxonomy.py` | Pure Python | 0 | 38 PE metrics + income-statement extension; label→metric mapping |
| Validator | `pipeline_a/validate.py` | Pure Python | 0 | Range / comparison / **reconciliation** (net = pretax − tax) error-checks |
| Variance | `pipeline_a/variance.py` | Pure Python | 0 | QoQ deltas vs prior period (≥10% flag) |
| Loaders + chunkers | `pipeline_b/loaders.py`, `chunkers.py` | Pure Python / embedding | 0 | Fixed-size, structure-aware, and **semantic** (embedding-based) chunking |
| Embedder | `pipeline_b/embed.py` | Nebius API | 0 | Qwen3-Embedding-8B, truncated to 1024-d (Matryoshka) |
| Vector store | `db/0001_rag_tables.sql` | Supabase pgvector | 0 | `rag_chunks` (dense + tsvector) + `rag_metrics`; persistent, incremental |
| Retriever | `pipeline_b/retrieve.py` | Similarity + BM25 | 0 | Hybrid dense + sparse + RRF + period metadata filter |
| Reranker | `pipeline_b/retrieve.py` | FlashRank (onnxruntime) | 0 | `ms-marco-MiniLM-L-12-v2` cross-encoder; calibrated scores |
| Generator | `pipeline_b/generate.py` | Claude `claude-sonnet-4-6` | 1 / answer | Cited answer / narrative; refusal-first |
| Judges (eval) | `pipeline_b/generate.py` | Claude | ~3 / question | Faithfulness · Context Precision · Context Recall |
| Orchestration | `graph.py` | LangGraph | — | Stateful graph + human `interrupt` confirm gate |
| UI | `app.py`, `ui.py` | Streamlit | — | Canvas-style ingest, confirm gate, Insights one-pager + Q&A |

---

## 4. Key design decisions

| Decision | Alternative rejected | Rationale |
|---|---|---|
| **Two pipelines** (deterministic numbers + RAG narrative) | All-RAG QA | Embedding retrieval over financial tables is lossy — the course measures 0.00 precision. Numbers must be exact, traceable, and reconciled; RAG is reserved for the "why." |
| **Supabase pgvector** | Pinecone | Shares a single Postgres, so vectors **and** structured metrics live in one DB; one fewer vendor. |
| **Nebius embeddings** (Qwen3-Embedding) | OpenAI / local | Course requirement; open-weight; OpenAI-compatible → 1-line swap. Truncated 4096 → 1024 via Matryoshka to fit an indexed pgvector column. |
| **FlashRank cross-encoder** | Claude-as-reranker / Cohere | Local, free, **calibrated** scores (better refusal), and onnxruntime-based — installs on Python 3.14 where torch does not. |
| **Human confirm gate** (LangGraph `interrupt`) | Auto-confirm | Product vision: the partner reviews and confirms, never fills a blank form. |
| **Custom LLM-judge eval** | `ragas` package | Avoids langchain-version / Python-3.14 dependency conflicts; metrics mirror RAGAS (faithfulness, context precision, context recall). |
| **Hybrid + period filter** | Pure dense | Dense alone confused quarters ("Q3 2025" → Q4 2024); metadata filtering on `period` fixes it deterministically. |

---

## 5. Evaluation

Full results in `eval/runs/report.md`; harness in `eval/run_eval.py`; 10 ground-truth questions with
verified reference answers + 3 refusal questions in `eval/questions.py`.

**A/B/C chunking + rerank comparison (LLM-judge, RAGAS-equivalent):**

| Metric | A: Fixed (no rerank) | B: Semantic (no rerank) | C: Semantic + Rerank |
|---|---|---|---|
| Faithfulness | 1.000 | 0.700 | 0.586 |
| Context Precision | 0.292 | **0.633** | 0.583 |
| Context Recall | 0.817 | 0.600 | 0.550 |

Refusal accuracy on unanswerable questions: **3/3**.

**Findings**
- **Semantic chunking lifts precision 0.29 → 0.63 vs fixed** — the course's core chunking finding
  reproduces (coherent passages = cleaner context). Fixed keeps the highest recall but the lowest
  precision (grabs the snippet *and* noise).
- **Reranking is roughly neutral at this small scale** (0.63 → 0.58): on an already-clean semantic
  candidate set, reranking top-6 → top-3 can drop a relevant chunk. Cross-encoder reranking pays off
  more with larger/noisier pools, and its calibrated scores still give a better refusal signal.
- **The headline:** numbers don't go through RAG at all. `scripts/run_numbers_demo.py` shows the
  table-as-text retrieval returning fragmented header/row chunks (the course's 0.00 failure), while
  Pipeline A returns the exact figure (`$13.5M`) with provenance (`Income Statement!E10`) and a passing
  reconciliation check.

---

## 6. Prompt library (excerpts)

**Cited answer (refusal-first):**
> You are a PE analyst assistant. Answer ONLY using the provided sources. Cite every factual claim with
> [S#]. Use no outside knowledge and invent no numbers. If the sources do not contain the answer, reply
> EXACTLY: "Not found in this company's documents." Be direct and factual; no flattery, no hedging.

**One-pager narrative (aggregation-first):**
> Use ONLY the confirmed metrics provided for any figure. Ground every qualitative claim in the sources
> and cite [S#]. Aggregation-first: describe what changed and the stated reasons; do NOT prescribe
> actions or speculate on causation beyond the sources. Return concise JSON.

**Faithfulness judge:** list each factual claim → mark supported/not by sources → `SCORE: <supported>/<total>`.

---

## 7. How this differs from a textbook RAG project

| | Course reference kit | This project |
|---|---|---|
| Goal | RAG QA over 10-Ks | Two-pipeline document intelligence → cited one-pager + Q&A |
| Numbers | Answered via RAG (fights table fragmentation) | **Deterministic extraction** (exact + reconciled + provenance) |
| Eval | RAGAS over 3 configs | LLM-judge equivalents over 3 configs + a deterministic-vs-RAG demo |
| Extras | — | Validation, variance, human confirm gate, LangGraph, persistence, Streamlit product |
| Rerank | FlashRank cross-encoder | FlashRank cross-encoder (same), + calibrated-score refusal |

**One-line thesis:** the course proves RAG fails on financial tables; this project is the answer —
*don't use RAG for the numbers.*
