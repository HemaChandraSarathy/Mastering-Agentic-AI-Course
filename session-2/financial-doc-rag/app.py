"""Streamlit demo UI for financial-doc-rag (multi-company, Supabase-backed).

Sidebar company switcher scopes three tabs —
Ingest / Review & confirm / Insights — to one company, or shows a Portfolio overview across
all companies. Everything persists in Supabase pgvector, scoped by company_id.

Run: streamlit run app.py   ->  http://localhost:8501
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
load_dotenv()

from portcoiq_rag import onepager
from portcoiq_rag.ingest import ingest_files
from portcoiq_rag.pipeline_a.models import ExtractedMetric, period_sort_key
from portcoiq_rag.pipeline_a.validate import validate
from portcoiq_rag.pipeline_a.variance import compute_variance
from portcoiq_rag.pipeline_b import generate, store
from portcoiq_rag.pipeline_b.retrieve import flashrank_rerank
from portcoiq_rag.taxonomy import ALL_METRICS
from portcoiq_rag.ui import (APP_CSS, coverage, hero_html, onepager_height, portfolio_html,
                             render_onepager_html, source_card)

REPO = Path(__file__).resolve().parent
SAMPLE_DIR = REPO / "corpus" / "sample"
COVERAGE_METRICS = ["revenue", "net_income", "eps_diluted", "total_costs_and_expenses",
                    "income_tax_expense", "ebitda", "cash", "net_debt", "headcount"]
PORTFOLIO = "▦ Portfolio (all companies)"


def _fmt_metric(mt: str, v: float) -> str:
    u = ALL_METRICS[mt].unit.value if mt in ALL_METRICS else ""
    if u == "$M":
        return f"${v:,.0f}M"
    if u == "%":
        return f"{v:.1f}%"
    if u == "x":
        return f"{v:.1f}x"
    return f"{v:,.0f}"


@st.cache_resource(show_spinner="Loading retriever from Supabase…")
def get_retriever(company_id):
    from portcoiq_rag.pipeline_b.index import build_supabase_retriever
    return build_supabase_retriever(company_id)


def _manifest() -> list[dict]:
    f = SAMPLE_DIR / "manifest.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def _sector_for(name: str) -> str:
    return next((c["sector"] for c in _manifest() if c["name"] == name), "")


def _reconstruct(rows: list[dict]) -> list[ExtractedMetric]:
    return [ExtractedMetric(
        raw_label=r.get("raw_label") or r["metric_type"], metric_type=r["metric_type"],
        period=r["period"], value=float(r["value"]), unit=r.get("unit"),
        source_file=r.get("source_file") or "", tab=r.get("tab"), cell_ref=r.get("cell_ref"),
        confidence=r.get("confidence"), confirmed=bool(r.get("confirmed")),
    ) for r in rows]


def _latest_by_type(rows: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for r in rows:
        mt = r["metric_type"]
        if mt not in latest or period_sort_key(r["period"]) > period_sort_key(latest[mt]["period"]):
            latest[mt] = r
    return latest


def main() -> None:
    st.set_page_config(page_title="Document Intelligence", layout="wide")
    st.markdown(APP_CSS, unsafe_allow_html=True)

    # ---- sidebar company switcher ----
    try:
        companies = store.list_companies()
    except Exception as e:
        st.error(f"Couldn't reach Supabase: {e}")
        companies = []
    name_to_id = {c["company"]: c["company_id"] for c in companies}
    options = [PORTFOLIO] + list(name_to_id.keys())
    st.sidebar.markdown("### 🏢 Company")
    sel = st.sidebar.selectbox("Company", options, label_visibility="collapsed", key="company_sel")
    is_portfolio = sel == PORTFOLIO
    company_id = None if is_portfolio else name_to_id.get(sel)
    company_name = None if is_portfolio else sel
    if not is_portfolio:
        st.sidebar.caption(_sector_for(company_name) or "—")
    st.sidebar.caption(f"{len(companies)} companies in store")

    # ---- Portfolio selected → the project one-pager (hero landing) ----
    if is_portfolio:
        cta = st.columns([4, 1])
        with cta[1]:
            if st.button("Load sample companies", use_container_width=True,
                         help="Loads 3 fictional companies (Meridian, Cobalt, Harbor)."):
                with st.spinner("Loading sample companies…"):
                    for co in _manifest():
                        ingest_files(sorted((REPO / co["dir"]).glob("*")), company=co["name"])
                get_retriever.clear()
                for k in [k for k in st.session_state if k.startswith("narrative_")]:
                    st.session_state.pop(k, None)
                st.rerun()
        entries = []
        for c in companies:
            cnt = store.counts(c["company_id"])
            entries.append({"name": c["company"], "sector": _sector_for(c["company"]),
                            "docs": cnt["documents"], "metrics": cnt["metrics"]})
        height = 1880 + (185 * ((len(entries) + 2) // 3) if entries else 0)
        components.html(hero_html(entries), height=height, scrolling=False)
        st.caption("Select a company in the sidebar to open its workspace (Ingest · Review · Insights).")
        return

    st.title(f"Document Intelligence — {company_name}")
    st.caption("Upload a portfolio company's documents — financials, transcripts, reports. "
               "Extracted, checked, and persisted in Supabase pgvector.")

    tab_ingest, tab_confirm, tab_onepager = st.tabs(
        ["1 · Ingest", "2 · Review & confirm", "3 · Insights"]
    )

    # ============================ TAB 1 — INGEST ============================
    with tab_ingest:
        tc1, tc2 = st.columns([2, 1])
        with tc1:
            up_company = st.text_input("Company for uploaded files",
                                       value=company_name or "", placeholder="Company name",
                                       label_visibility="collapsed")
        with tc2:
            do_sample = st.button("Load sample companies", use_container_width=True,
                                  help="Loads 3 fictional companies (Meridian, Cobalt, Harbor).")

        ups = st.file_uploader("Drop files here  —  PDF, Excel, text",
                               accept_multiple_files=True, type=["pdf", "xlsx", "xls", "txt", "md"],
                               key="uploader")
        do_upload = bool(ups) and st.button(f"Ingest {len(ups)} file(s)", type="primary")

        if do_sample:
            with st.spinner("Extract → embed → persist (3 companies)…"):
                for co in _manifest():
                    files = sorted((REPO / co["dir"]).glob("*"))
                    ingest_files(files, company=co["name"])
            get_retriever.clear()
            for k in [k for k in st.session_state if k.startswith("narrative_")]:
                st.session_state.pop(k, None)
            st.success("Loaded sample companies. Pick one in the sidebar.")
            st.rerun()
        if do_upload:
            tmp = REPO / "_scratch" / "uploads"
            tmp.mkdir(parents=True, exist_ok=True)
            paths = []
            for u in ups:
                p = tmp / u.name
                p.write_bytes(u.getbuffer())
                paths.append(p)
            with st.spinner("Processing files → Supabase…"):
                s = ingest_files(paths, company=(up_company or "My Company"))
            get_retriever.clear()
            st.session_state.pop(f"narrative_{s['company_id']}", None)
            st.success(f"Added {s['metrics_stored']} metrics, {s['chunks_stored']} chunks to "
                       f"**{s['company']}**.")
            st.rerun()

        # sources + coverage (scoped to selected company, or all for portfolio)
        try:
            docs = store.list_documents(company_id)
            chunks = store.load_chunks(company_id)
            metrics = store.load_metrics(company_id)
        except Exception as e:
            st.warning(f"Couldn't read Supabase: {e}")
            docs, chunks, metrics = [], [], []

        chunk_ct = Counter(c.source_file for c in chunks)
        metric_ct = Counter(r["source_file"] for r in metrics)
        files: dict[str, tuple] = {}
        for d in docs:
            files[d["source_file"]] = (d.get("doc_type"), d.get("period"),
                                       chunk_ct.get(d["source_file"], 0), metric_ct.get(d["source_file"], 0))
        for r in metrics:
            sf = r["source_file"]
            if sf not in files:
                files[sf] = ("financials", None, chunk_ct.get(sf, 0), metric_ct.get(sf, 0))

        st.markdown(f"**Sources** {'(all companies)' if is_portfolio else f'— {company_name}'}")
        if files:
            st.markdown("".join(source_card(n, dt, pe, ch, me) for n, (dt, pe, ch, me) in files.items()),
                        unsafe_allow_html=True)
        else:
            st.info("No files yet. Load the sample companies or drop your own.")

        latest = _latest_by_type(metrics)
        cov_rows = [(ALL_METRICS[mt].label if mt in ALL_METRICS else mt,
                     _fmt_metric(mt, latest[mt]["value"]) if mt in latest else None)
                    for mt in COVERAGE_METRICS]
        if not is_portfolio:
            st.markdown(coverage(cov_rows), unsafe_allow_html=True)

        with st.expander("Manage data"):
            if st.button("Clear all data"):
                store.clear_all()
                get_retriever.clear()
                for k in [k for k in st.session_state if k.startswith("narrative_")]:
                    st.session_state.pop(k, None)
                st.success("Cleared all data.")
                st.rerun()

    # ======================= TAB 2 — REVIEW & CONFIRM =======================
    with tab_confirm:
        if is_portfolio:
            st.info("Select a company in the sidebar to review its metrics.")
        else:
            rows = store.load_metrics(company_id)
            if not rows:
                st.info(f"No metrics for {company_name} yet — ingest on Tab 1.")
            else:
                mets = _reconstruct(rows)
                df = pd.DataFrame([{
                    "confirm": True, "metric_type": m.metric_type, "period": m.period,
                    "value": m.value, "unit": m.unit, "source": (m.cell_ref or ""),
                } for m in mets])
                st.caption(f"{company_name} — loaded from Supabase. Edit a value to correct a mis-key; "
                           "untick **confirm** to exclude.")
                edited = st.data_editor(df, use_container_width=True, hide_index=True,
                                        key="confirm_editor",
                                        column_config={"confirm": st.column_config.CheckboxColumn()})
                confirmed = [ExtractedMetric(
                    raw_label=r["metric_type"], metric_type=r["metric_type"], period=r["period"],
                    value=float(r["value"]), unit=r["unit"], source_file="(supabase)",
                    cell_ref=r["source"], confirmed=True,
                ) for _, r in edited.iterrows() if r["confirm"]]
                st.session_state[f"confirmed_{company_id}"] = [m.model_dump() for m in confirmed]
                flags = validate(confirmed)
                st.markdown("**Validation**")
                if not flags:
                    st.success("All reconciliation identities hold.")
                for f in flags:
                    badge = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(f.severity, "•")
                    st.write(f"{badge} **{f.period}** — {f.message}")

    # =========================== TAB 3 — INSIGHTS ===========================
    with tab_onepager:
        if is_portfolio:
            st.subheader("Portfolio overview")
            entries = []
            for c in companies:
                rows = store.load_metrics(c["company_id"])
                latest = _latest_by_type(rows)
                headline = [(ALL_METRICS[mt].label, _fmt_metric(mt, latest[mt]["value"]))
                            for mt in ("revenue", "net_income", "ebitda", "leverage_ratio")
                            if mt in latest][:3]
                cnt = store.counts(c["company_id"])
                entries.append({"name": c["company"], "sector": _sector_for(c["company"]),
                                "headline": headline, "docs": cnt["documents"], "metrics": cnt["metrics"]})
            if entries:
                components.html(portfolio_html(entries), height=120 + 220 * ((len(entries) + 2) // 3),
                                scrolling=False)
            else:
                st.info("No companies yet — load the sample on Tab 1.")
        else:
            st.subheader(f"Insights one-pager — {company_name}")
            rows = store.load_metrics(company_id)
            ckey = f"confirmed_{company_id}"
            metrics = ([ExtractedMetric(**d) for d in st.session_state[ckey]]
                       if st.session_state.get(ckey) else _reconstruct(rows))
            if not metrics:
                st.info(f"No metrics for {company_name} yet — ingest on Tab 1.")
            else:
                flags = validate(metrics)
                variance = compute_variance(metrics)
                mapped = [m for m in metrics if m.metric_type]
                latest = sorted({m.period for m in mapped}, key=period_sort_key)[-1] if mapped else None
                nkey = f"narrative_{company_id}"

                if nkey not in st.session_state and latest:
                    retr = get_retriever(company_id)
                    if retr.chunks:
                        var = compute_variance(metrics)
                        mlines = [f"{ALL_METRICS[m.metric_type].label}: {m.value:,.0f} {m.unit or ''}".strip()
                                  for m in mapped if m.period == latest]
                        vlines = [f"{ALL_METRICS[v.metric_type].label}: {v.qoq_pct*100:+.1f}% QoQ"
                                  for v in var if v.period == latest and v.qoq_pct is not None]
                        q = f"What changed for {company_name} in {latest} and why?"
                        with st.spinner("Retrieving (pgvector) → reranking → generating cited narrative…"):
                            hits = flashrank_rerank(q, retr.search(q, k=8), top_n=4)
                            st.session_state[nkey] = generate.generate_narrative(mlines, vlines, hits)

                if st.session_state.get(nkey) and st.button("↻ Regenerate narrative"):
                    st.session_state.pop(nkey, None); st.rerun()

                corpus_files = sorted({m.source_file for m in metrics if m.source_file} |
                                      {d["source_file"] for d in store.list_documents(company_id)})
                insight = onepager.assemble(metrics, flags, variance, company=company_name,
                                            sector=_sector_for(company_name), corpus_files=corpus_files,
                                            narrative=st.session_state.get(nkey))
                components.html(render_onepager_html(insight), height=onepager_height(insight),
                                scrolling=False)

                with st.expander("Ask a question (cited Q&A over pgvector)"):
                    qa = st.text_input("Question", placeholder="e.g. What did management say about margins?")
                    if qa:
                        retr = get_retriever(company_id)
                        with st.spinner("Retrieving (pgvector) → reranking → answering…"):
                            st.markdown(generate.ask(qa, retr))


if __name__ == "__main__":
    main()
