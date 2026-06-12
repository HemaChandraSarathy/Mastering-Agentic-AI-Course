"""Load the narrative corpus and compare the two chunking strategies (no keys needed).

Usage: python scripts/run_chunking.py
Set CORPUS_DIR in .env, or it falls back to the Conoco Sample Data path.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

from portcoiq_rag.pipeline_b.loaders import load_corpus
from portcoiq_rag.pipeline_b.chunkers import fixed_chunks, structural_chunks

load_dotenv()
DEFAULT = r"C:\Users\hemac\OneDrive\Documents\Aish Srinivasan Gen Academy Workshop\Conoco Sample Data"
corpus = os.getenv("CORPUS_DIR_RAW", DEFAULT)

docs = load_corpus(corpus, doc_types={"earnings_transcript", "analyst_report"})
print(f"Loaded {len(docs)} text docs:\n")
for d in docs:
    print(f"  {d.source_file:<42} type={d.doc_type:<18} period={d.period or '-':<8} pages={len(d.pages)}")

print("\n=== CHUNKING COMPARISON ===")
print(f"{'doc':<42}{'fixed':>8}{'structural':>12}")
for d in docs:
    fx = fixed_chunks(d)
    st = structural_chunks(d)
    print(f"{d.source_file:<42}{len(fx):>8}{len(st):>12}")

# show a couple of structural chunks from the transcript for a sanity check
tx = next((d for d in docs if d.doc_type == "earnings_transcript"), None)
if tx:
    print(f"\n=== sample structural chunks — {tx.source_file} ===")
    for c in structural_chunks(tx)[:4]:
        sect = (c.section or "")[:60]
        print(f"\n[chunk {c.chunk_index} | p{c.page} | ~{c.approx_tokens} tok | section: {sect!r}]")
        print("  " + c.content[:240].replace("\n", " ") + "...")
