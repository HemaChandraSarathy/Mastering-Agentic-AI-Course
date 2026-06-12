# Mastering Agentic AI

Course projects and exercises for *Mastering Agentic AI*.

## Sessions

### Session 1 — [MoveIt](./session-1/moveit)
A Streamlit + LangChain fitness accountability app with AI-powered companions.
Users pick a personality (Simon Sinek, Gordon Ramsay, Golden Retriever, etc.) or
create a custom one, then get personalised motivation throughout their day.

- **Stack:** Streamlit · LangChain · ChatAnthropic (Claude)
- **Run it:** `pip install -r requirements.txt`, add your `ANTHROPIC_API_KEY` to
  `.streamlit/secrets.toml`, then `streamlit run app.py`
- See [`session-1/moveit/README.md`](./session-1/moveit/README.md) for details.

### Session 2 — [Financial Document Intelligence (RAG)](./session-2/financial-doc-rag)
A two-pipeline RAG system that turns a portfolio company's document folder into a cited,
analyst-confirmed insights one-pager. **Numbers are extracted deterministically** (Excel cells,
text-PDF tables, and image-PDF OCR via LiteParse) — never from a vector search — then validated and
reconciled; **narrative is answered by RAG** (hybrid retrieval + rerank over Supabase pgvector) with a
refusal path. Includes two golden eval sets (retrieval quality + extraction accuracy).

- **Stack:** LangChain + LangGraph · Supabase pgvector · Nebius (embeddings) · Anthropic `claude-sonnet-4-6` ·
  pdfplumber / pandas / LiteParse OCR (extraction) · Streamlit (UI)
- **Run it:** `pip install -r requirements.txt`, copy `.env.example` → `.env` and fill keys, then
  `streamlit run app.py`
- See [`session-2/financial-doc-rag/README.md`](./session-2/financial-doc-rag/README.md) for details.
