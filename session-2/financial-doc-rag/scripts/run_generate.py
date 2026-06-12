"""End-to-end generation test: retrieve -> rerank -> cited Q&A (+refusal) -> narrative.

Usage: python scripts/run_generate.py
Uses cached embeddings from run_hybrid.py (run that first, or it embeds here).
"""
import os
import pickle
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "eval"))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

from portcoiq_rag.pipeline_a.extract import extract_from_excel
from portcoiq_rag.pipeline_a.variance import compute_variance
from portcoiq_rag.pipeline_a.models import period_sort_key
from portcoiq_rag.pipeline_b.loaders import load_corpus
from portcoiq_rag.pipeline_b.chunkers import structural_chunks
from portcoiq_rag.pipeline_b.embed import embed_chunks
from portcoiq_rag.pipeline_b.retrieve import HybridRetriever, InMemoryDenseRetriever
from portcoiq_rag.pipeline_b import generate
from portcoiq_rag.taxonomy import ALL_METRICS

load_dotenv()
CORPUS = os.getenv("CORPUS_DIR_RAW", r"C:\Users\hemac\OneDrive\Documents\Aish Srinivasan Gen Academy Workshop\Conoco Sample Data")
CACHE = REPO / "_scratch" / "emb_cache.pkl"

docs = load_corpus(CORPUS, doc_types={"earnings_transcript", "analyst_report"})
chunks = [c for d in docs for c in structural_chunks(d)]
cache = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
need = [c for c in chunks if (c.source_file, c.chunk_index, len(c.content)) not in cache]
if need:
    embed_chunks(need)
    for c in need:
        cache[(c.source_file, c.chunk_index, len(c.content))] = c.embedding
    CACHE.parent.mkdir(exist_ok=True); CACHE.write_bytes(pickle.dumps(cache))
for c in chunks:
    c.embedding = cache[(c.source_file, c.chunk_index, len(c.content))]

retr = HybridRetriever(chunks, dense=InMemoryDenseRetriever(chunks))

print("=== CITED Q&A (retrieve -> rerank -> answer) ===")
for q in ["Who hosted the Q3 2025 earnings call and what roles do they hold?",
          "What did management say about LNG in Q3 2025?",
          "What is ConocoPhillips' dividend guidance for 2027?"]:   # last = refusal expected
    hits = generate.rerank(q, retr.search(q, k=8), top_n=4)
    ans = generate.answer_question(q, hits)
    print(f"\nQ: {q}\nA: {ans}")

print("\n\n=== ONE-PAGER NARRATIVE ===")
metrics = extract_from_excel(REPO / "corpus" / "ConocoPhillips_SYNTHETIC_financials.xlsx")
var = compute_variance(metrics)
mapped = [m for m in metrics if m.metric_type]
latest = sorted({m.period for m in mapped}, key=period_sort_key)[-1]
metric_lines = [f"{ALL_METRICS[m.metric_type].label}: {m.value:,.0f} ({m.unit})"
                for m in mapped if m.period == latest]
var_lines = [f"{ALL_METRICS[v.metric_type].label}: {v.qoq_pct*100:+.1f}% QoQ"
             for v in var if v.period == latest and v.qoq_pct is not None]
nhits = generate.rerank("What changed for ConocoPhillips in Q3 2025 and why?",
                        retr.search("What changed for ConocoPhillips in Q3 2025 and why?", k=8), top_n=4)
narr = generate.generate_narrative(metric_lines, var_lines, nhits)
print(f"\nsentiment: {narr['sentiment']}")
print(f"summary  : {narr['summary']}")
print(f"headwinds: {narr.get('headwinds')}")
print(f"tailwinds: {narr.get('tailwinds')}")
