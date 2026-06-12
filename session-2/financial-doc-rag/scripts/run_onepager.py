"""Assemble the Insights one-pager from Pipeline A and write a standalone HTML preview.

Usage: python scripts/run_onepager.py
Writes _scratch/preview.html — open it in a browser to see the design-system one-pager.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

import os

from dotenv import load_dotenv

from portcoiq_rag.pipeline_a.extract import extract_from_excel
from portcoiq_rag.pipeline_a.validate import validate
from portcoiq_rag.pipeline_a.variance import compute_variance
from portcoiq_rag.pipeline_a.models import period_sort_key
from portcoiq_rag import onepager
from portcoiq_rag.taxonomy import ALL_METRICS
from portcoiq_rag.ui import ROOT_CSS, render_onepager_html

load_dotenv()
REPO = Path(__file__).resolve().parents[1]
xlsx = REPO / "corpus" / "ConocoPhillips_SYNTHETIC_financials.xlsx"

metrics = extract_from_excel(xlsx)
flags = validate(metrics)
variance = compute_variance(metrics)
corpus_files = [xlsx.name, "Q3 2025 Earnings Transcript.pdf", "ARGUS Report on COP.pdf"]

# Pipeline B: generate the cited narrative (set RAG=0 to skip and produce a numbers-only preview).
narrative = None
if os.getenv("RAG", "1") == "1":
    from portcoiq_rag.pipeline_b.index import build_retriever
    from portcoiq_rag.pipeline_b import generate
    mapped = [m for m in metrics if m.metric_type]
    latest = sorted({m.period for m in mapped}, key=period_sort_key)[-1]
    mlines = [f"{ALL_METRICS[m.metric_type].label}: {m.value:,.0f} {m.unit or ''}".strip()
              for m in mapped if m.period == latest]
    vlines = [f"{ALL_METRICS[v.metric_type].label}: {v.qoq_pct*100:+.1f}% QoQ"
              for v in variance if v.period == latest and v.qoq_pct is not None]
    retr = build_retriever(os.getenv("CORPUS_DIR_RAW",
                           r"C:\Users\hemac\OneDrive\Documents\Aish Srinivasan Gen Academy Workshop\Conoco Sample Data"),
                           REPO / "_scratch" / "emb_cache.pkl")
    q = f"What changed for ConocoPhillips in {latest} and why?"
    print("generating narrative via Pipeline B…")
    narrative = generate.generate_narrative(mlines, vlines, generate.rerank(q, retr.search(q, k=8), 4))

insight = onepager.assemble(metrics, flags, variance, corpus_files=corpus_files,
                            generated_at="2026-06-10 09:00", narrative=narrative)

print(f"company={insight.company}  period={insight.period}  metrics={len(insight.metrics)}")
for m in insight.metrics:
    print(f"  {m.name:<28}{m.value:>12}  QoQ {m.qoq:>8}  [{m.flag}]  {m.provenance}")
print(f"  dataQuality: {insight.dataQuality['docsAvailable']}/{insight.dataQuality['docsExpected']} docs; "
      f"gaps={insight.dataQuality['gaps']}")

out = REPO / "_scratch" / "preview.html"
out.parent.mkdir(exist_ok=True)
out.write_text(render_onepager_html(insight), encoding="utf-8")  # now a complete HTML doc
print(f"\nwrote {out}")
