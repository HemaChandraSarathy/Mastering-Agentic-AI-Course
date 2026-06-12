# Before / After — what improved and where to see it

Two parts: (1) the **RAG/eval upgrades** driven by comparing against the course solution kit, and
(2) the **product/UI changes** made this session. Each row says exactly where to look.

> **How to run things** (from `C:\Users\hemac\Documents\financial-doc-rag`):
> - App: `.\.venv\Scripts\python.exe -m streamlit run app.py` → http://localhost:8501
> - Eval: `.\.venv\Scripts\python.exe eval\run_eval.py`
> - Numbers demo: `.\.venv\Scripts\python.exe scripts\run_numbers_demo.py`
> - LangGraph: `.\.venv\Scripts\python.exe scripts\run_graph.py`

---

## Part 1 — RAG / evaluation upgrades (vs the course kit)

| Area | Before | After | Where to see it |
|---|---|---|---|
| **Eval rigor** | Thin harness: hit@3 on ~4 questions, faithfulness only, no verified answers | **RAGAS-equivalent**: faithfulness + **context precision + recall**, **10 ground-truth questions with verified reference answers** + 3 refusal, full **A/B/C table** | `eval\run_eval.py`, `eval\questions.py` → run it; read **`eval\runs\report.md`** |
| **Chunking strategies** | Fixed-size + heuristic "structural" only | Added a **true embedding-based semantic chunker** (sentence-distance breakpoints) → 31 coherent chunks; eval shows **precision 0.29 → 0.63 vs fixed** | `src\portcoiq_rag\pipeline_b\chunkers.py` (`semantic_chunks`); numbers in `report.md` |
| **Reranker** | Claude-as-reranker (slow, pricey, uncalibrated) | **FlashRank cross-encoder** (`ms-marco-MiniLM`, onnxruntime, local, free, **calibrated scores**) — and wired into the app | `pipeline_b\retrieve.py` (`flashrank_rerank`); used in app Q&A + narrative |
| **Refusal** | LLM-only "I don't know" | FlashRank's calibrated score gives a **cheap pre-refusal** (skips a Claude call when nothing is relevant) | `pipeline_b\generate.py` (`ask`, `min_score`) — try an off-topic question in the app's **Q&A box** |
| **Numbers vs RAG** | Architectural claim argued in words | A **runnable demonstration**: RAG retrieves fragmented table chunks; Pipeline A returns exact `$13.5M` + provenance + passing reconciliation | **`scripts\run_numbers_demo.py`** — run it |
| **Writeup** | Scattered across plan + eval README | One **polished project doc** (overview, architecture, component table, design decisions, eval, prompts) | **`docs\PROJECT_DOC.md`** |

**The eval result (the headline table):**

| Metric | A: Fixed | B: Semantic | C: Semantic + Rerank |
|---|---|---|---|
| Faithfulness | 1.000 | 0.700 | 0.586 |
| Context Precision | 0.292 | **0.633** | 0.583 |
| Context Recall | 0.817 | 0.600 | 0.550 |

→ Semantic chunking lifts precision (0.29 → 0.63); reranking is neutral at this small scale; refusal 3/3.

---

## Part 2 — Product / UI changes (this session)

| Area | Before | After | Where to see it |
|---|---|---|---|
| **Branding** | Branded header, Conoco everywhere | Generic **"Document Intelligence"**, no brand, no Conoco | App header at http://localhost:8501 |
| **Sample data** | Real ConocoPhillips public filings | **Fictional Meridian Industrial Components** (fabricated, labeled), richer metric set | `scripts\make_sample_data.py`; **Tab 1 → "Try sample dataset"** |
| **Ingest tab** | Plain list + buttons | **Canvas-style**: dashed drop zone + source cards + **coverage tracker** (✓/○) | **Tab 1**; static preview `_scratch\canvas_preview.png` |
| **Persistence** | In-memory only (forgot on restart) | **Supabase pgvector** — persists, incremental upload, "Clear all data" | **Tab 1** (counts, uploader, Manage data); retrieval reads from pgvector |
| **One-pager fidelity** | My approximation; **broke in-app** (iframe lacked design tokens) | Faithful copy of an InsightsPanel-style layout (card stack, Key Metrics table, sentiment, headwinds/tailwinds); tokens embedded so it renders in-app | **Tab 3**; static preview `_scratch\preview.png` |
| **One-pager scroll** | Inner scrollbar + page scroll | **No inner scroll** — sizes to content, page scrolls only | **Tab 3** |
| **Narrative** | Click a button to generate | **Auto-generates** on load (cached), regenerates on new ingest, "↻ Regenerate" | **Tab 3** |
| **Deploy button** | Streamlit "Deploy" + dev toolbar visible | Hidden (clean product view) | top-right of the app (gone) |
| **DNS reliability** | App broke intermittently (`getaddrinfo failed`) | Always-on DoH host-pinning — robust to the flaky router | `src\portcoiq_rag\_dns.py` (no visible UI; app just stays connected) |

---

## Quick tour to see everything

1. **App** → http://localhost:8501
   - **Tab 1 (Ingest):** Canvas drop zone, source cards, coverage tracker, "Try sample dataset", "Clear all data"
   - **Tab 2 (Review & confirm):** editable metrics + reconciliation check
   - **Tab 3 (One-pager):** the cited Insights one-pager (auto narrative) + Q&A box
2. **Eval table:** `eval\runs\report.md` (or re-run `eval\run_eval.py`)
3. **Numbers headline:** run `scripts\run_numbers_demo.py`
4. **Writeup:** `docs\PROJECT_DOC.md`
5. **Static previews (no run needed):** `_scratch\preview.png` (one-pager), `_scratch\canvas_preview.png` (ingest cards)
