"""Embed the corpus via Nebius, then compare BM25 vs dense vs hybrid retrieval.

Caches chunk embeddings to _scratch/emb_cache.pkl so re-runs don't re-pay Nebius.
Usage: python scripts/run_hybrid.py
"""
import os
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

from portcoiq_rag.pipeline_b.loaders import load_corpus
from portcoiq_rag.pipeline_b.chunkers import structural_chunks
from portcoiq_rag.pipeline_b.embed import embed_chunks
from portcoiq_rag.pipeline_b.retrieve import BM25Retriever, InMemoryDenseRetriever, HybridRetriever
from questions import QUESTIONS

load_dotenv()
DEFAULT = r"C:\Users\hemac\OneDrive\Documents\Aish Srinivasan Gen Academy Workshop\Conoco Sample Data"
corpus = os.getenv("CORPUS_DIR_RAW", DEFAULT)
CACHE = Path(__file__).resolve().parents[1] / "_scratch" / "emb_cache.pkl"

docs = load_corpus(corpus, doc_types={"earnings_transcript", "analyst_report"})
chunks = [c for d in docs for c in structural_chunks(d)]
print(f"{len(chunks)} chunks from {len(docs)} docs")

# embed with cache keyed by (source_file, chunk_index, content length)
cache = {}
if CACHE.exists():
    cache = pickle.loads(CACHE.read_bytes())
to_embed = [c for c in chunks if (c.source_file, c.chunk_index, len(c.content)) not in cache]
if to_embed:
    print(f"embedding {len(to_embed)} new chunks via Nebius...")
    embed_chunks(to_embed)
    for c in to_embed:
        cache[(c.source_file, c.chunk_index, len(c.content))] = c.embedding
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_bytes(pickle.dumps(cache))
for c in chunks:
    c.embedding = cache[(c.source_file, c.chunk_index, len(c.content))]
print("embeddings ready.\n")

bm25 = BM25Retriever(chunks)
dense = InMemoryDenseRetriever(chunks)
hybrid = HybridRetriever(chunks, dense=dense)


def top(retr, q):
    hits = retr.search(q, k=3)
    if not hits:
        return "(none)"
    c = hits[0].chunk
    return f"{c.source_file[:28]:28} p{c.page} | {(c.section or '')[:32]:32}"


# focus on the answerable questions where semantics should help
for q in [x for x in QUESTIONS if x.answerable][:8]:
    print(f"[{q.id}] {q.question}")
    print(f"   BM25  : {top(bm25, q.question)}")
    print(f"   DENSE : {top(dense, q.question)}")
    print(f"   HYBRID: {top(hybrid, q.question)}")
    print()
