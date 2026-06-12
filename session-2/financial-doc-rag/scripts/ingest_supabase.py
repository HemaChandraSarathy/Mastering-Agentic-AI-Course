"""Persist the corpus to Supabase pgvector, then verify retrieval via the RPC.

Run after the migration is applied and DNS resolves:
    python scripts/ingest_supabase.py
Reuses cached embeddings from _scratch/emb_cache.pkl.
"""
import os
import pickle
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

from portcoiq_rag.pipeline_a.extract import extract_from_excel
from portcoiq_rag.pipeline_a.validate import validate
from portcoiq_rag.pipeline_a.variance import compute_variance
from portcoiq_rag.pipeline_b.loaders import load_corpus
from portcoiq_rag.pipeline_b.chunkers import structural_chunks
from portcoiq_rag.pipeline_b.embed import embed_chunks
from portcoiq_rag.pipeline_b import store

load_dotenv()
CORPUS = os.getenv("CORPUS_DIR_RAW", r"C:\Users\hemac\OneDrive\Documents\Aish Srinivasan Gen Academy Workshop\Conoco Sample Data")
CACHE = REPO / "_scratch" / "emb_cache.pkl"
XLSX = REPO / "corpus" / "ConocoPhillips_SYNTHETIC_financials.xlsx"

# --- chunks + embeddings (cached) ---
docs = load_corpus(CORPUS, doc_types={"earnings_transcript", "analyst_report"})
chunks = [c for d in docs for c in structural_chunks(d)]
cache = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
key = lambda c: ("structural", c.source_file, c.chunk_index, len(c.content))
need = [c for c in chunks if key(c) not in cache]
if need:
    print(f"embedding {len(need)} chunks via Nebius...")
    embed_chunks(need)
    for c in need:
        cache[key(c)] = c.embedding
    CACHE.parent.mkdir(exist_ok=True); CACHE.write_bytes(pickle.dumps(cache))
for c in chunks:
    c.embedding = cache[key(c)]

print(f"storing {len(chunks)} chunks to Supabase...")
n = store.store_chunks(chunks)
print(f"  stored {n} rag_chunks rows.")

# --- confirmed metrics ---
metrics = extract_from_excel(XLSX)
flags = validate(metrics)
var = compute_variance(metrics)
sev = {(f.metric_type, f.period): f.severity for f in flags if f.metric_type and f.period}
vpct = {(v.metric_type, v.period): v.qoq_pct for v in var}
rows = [{
    "company": "ConocoPhillips", "metric_type": m.metric_type, "raw_label": m.raw_label,
    "period": m.period, "value": m.value, "unit": m.unit, "source_file": m.source_file,
    "tab": m.tab, "cell_ref": f"{m.tab}!{m.cell_ref}",
    "validation_status": sev.get((m.metric_type, m.period), "ok"),
    "variance_pct": vpct.get((m.metric_type, m.period)), "confirmed": True,
} for m in metrics if m.metric_type]
store.store_metrics(rows)
print(f"  stored {len(rows)} rag_metrics rows.")

# --- verify retrieval from pgvector ---
print("\nverifying pgvector retrieval via RPC:")
dense = store.SupabaseDenseRetriever()
for h in dense.search("What did management say about LNG in Q3 2025?", k=3):
    print(f"  {h.score:.3f}  {h.chunk.source_file} p{h.chunk.page} | {(h.chunk.section or '')[:40]}")
