# financial-doc-rag

**Gen Academy — Mastering Agentic AI · Week 2 RAG Project**
A **Financial Document Intelligence Pipeline**: drop a portfolio company's document folder and get a
cited, analyst-confirmed insights one-pager — numbers extracted deterministically, narrative answered
by RAG, with provenance on every figure and claim.

---

> ⚠️ **Data disclaimer.** This project uses **ConocoPhillips public SEC filings** as a *labeled
> placeholder* for a private portfolio company's document folder. The figures are real public-company
> data; they are **not** real customer data and are used only because private portco data is
> unavailable. The synthetic Excel in `corpus/` re-keys those same real figures into a deliberately messy
> format — the **numbers are real, the spreadsheet layout is fabricated** to exercise the ingestion path.

---

## What it does

Drop a portfolio company's document folder → in <10 min get a **first-draft, analyst-confirmed Insights
one-pager** where every figure and claim cites its source document + page.

Two pipelines, deliberately separate:

- **Pipeline A — numbers (DETERMINISTIC, not RAG).** Table parse (`pdfplumber` / `pandas`) →
  normalize/map to a canonical metric taxonomy → validation (thresholds + reconciliation) → variance vs
  prior quarter. **No embeddings touch the numbers** — a mark must never come from a similarity search.
- **Pipeline B — narrative (RAG).** Chunk / embed (Nebius) / retrieve (hybrid + rerank over Supabase
  pgvector) the transcripts, analyst reports, and news → cited "why," with a refusal path.
- **Human review & confirm gate** between extraction and the one-pager: the analyst confirms or edits
  every figure (and spot-verifies against the SEC filing) before it flows into the brief.

Output is assembled into a `CompanyInsightData` one-pager shape and rendered in a Streamlit UI with a
custom editorial design system (linen background, single accent, serif/mono type).

## Architecture

```
corpus/ ──▶ Pipeline A (deterministic numbers) ─┐
       └──▶ Pipeline B (narrative RAG) ──────────┤
                                                 ▼
                      Human review & confirm gate
                                                 ▼
            Insights one-pager (CompanyInsightData, cited)
```

## Layout

```
financial-doc-rag/
├── corpus/                     # Conoco Sample Data (copied) + synthetic messy Excel
├── src/portcoiq_rag/
│   ├── taxonomy.py             # canonical metric set + label→metric mapping
│   ├── pipeline_a/             # extraction → validate → variance (deterministic)
│   ├── pipeline_b/             # ingest → chunk → embed → retrieve (RAG)
│   ├── graph.py                # LangGraph orchestration + confirm gate
│   ├── onepager.py             # assemble CompanyInsightData
│   └── clients.py              # Supabase / Nebius / Anthropic clients
├── scripts/
│   └── make_synthetic_excel.py # build the labeled messy .xlsx from real Conoco figures
├── eval/                       # narrative-RAG golden set + extraction golden set + chunking/rerank reports
├── app.py                      # Streamlit demo UI
├── .streamlit/config.toml
├── requirements.txt
└── .env.example
```

## Setup

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                               # fill in keys
```

Required env (see `.env.example`): `NEBIUS_API_KEY`, `ANTHROPIC_API_KEY`, `SUPABASE_URL`,
`SUPABASE_SERVICE_KEY`, `LANGSMITH_API_KEY` (optional, for tracing).

## Run

```bash
streamlit run app.py            # → http://localhost:8501
```

## Stack

LangChain + LangGraph · Supabase pgvector · Nebius Token Factory (embeddings) ·
Anthropic `claude-sonnet-4-6` (generation) · pdfplumber + pandas (Excel / text-PDF tables) ·
LiteParse OCR (image-only PDFs, local, no keys) · LangSmith (tracing) · Streamlit (UI).
