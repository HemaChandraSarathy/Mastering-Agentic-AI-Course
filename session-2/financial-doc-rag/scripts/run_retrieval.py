"""Build chunks from the corpus, index with BM25, and run the eval questions (no keys).

For each question: print the top retrieved chunk (source + section) or REFUSE if the top
score is below threshold. Checks that unanswerable questions correctly refuse.

Usage: python scripts/run_retrieval.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

from portcoiq_rag.pipeline_b.loaders import load_corpus
from portcoiq_rag.pipeline_b.chunkers import structural_chunks
from portcoiq_rag.pipeline_b.retrieve import BM25Retriever
from questions import QUESTIONS

load_dotenv()
DEFAULT = r"C:\Users\hemac\OneDrive\Documents\Aish Srinivasan Gen Academy Workshop\Conoco Sample Data"
corpus = os.getenv("CORPUS_DIR_RAW", DEFAULT)
MIN_SCORE = 2.0   # below this top BM25 score -> refuse (tunable)

docs = load_corpus(corpus, doc_types={"earnings_transcript", "analyst_report"})
chunks = [c for d in docs for c in structural_chunks(d)]
print(f"Indexed {len(chunks)} chunks from {len(docs)} docs (BM25, sparse).\n")

retr = BM25Retriever(chunks)
correct_refusals = 0
for q in QUESTIONS:
    hits = retr.search(q.question, k=3)
    top = hits[0] if hits else None
    refused = (top is None) or (top.score < MIN_SCORE)
    tag = "REFUSE" if refused else "ANSWER"
    print(f"[{q.id}] {tag:<7} ({q.category}, answerable={q.answerable})  {q.question}")
    if not refused:
        c = top.chunk
        sect = (c.section or "")[:48]
        print(f"        -> {c.source_file} p{c.page} | {sect!r} | score={top.score:.1f}")
        print(f"           {c.content[:150].strip()}...")
    if (not q.answerable) and refused:
        correct_refusals += 1

n_unans = sum(1 for q in QUESTIONS if not q.answerable)
print(f"\nRefusal accuracy on unanswerable: {correct_refusals}/{n_unans}")
