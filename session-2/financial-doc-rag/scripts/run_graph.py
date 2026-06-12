"""Run the LangGraph pipeline, demonstrating the human-in-the-loop confirm gate.

Flow: extract → validate → variance → [PAUSE for review] → resume → generate → assemble.
Usage: python scripts/run_graph.py
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from langgraph.types import Command

from portcoiq_rag.graph import build_graph
from portcoiq_rag.pipeline_b.index import build_retriever

load_dotenv()
CORPUS = os.getenv("CORPUS_DIR_RAW", r"C:\Users\hemac\OneDrive\Documents\Aish Srinivasan Gen Academy Workshop\Conoco Sample Data")
XLSX = REPO / "corpus" / "ConocoPhillips_SYNTHETIC_financials.xlsx"
CACHE = REPO / "_scratch" / "emb_cache.pkl"

print("building retriever (cached embeddings)…")
retriever = build_retriever(CORPUS, CACHE)
graph = build_graph(retriever)

config = {"configurable": {"thread_id": "demo-1"}}
init = {"xlsx_path": str(XLSX),
        "corpus_files": [XLSX.name, "Q3 2025 Earnings Transcript.pdf", "ARGUS Report on COP.pdf"],
        "auto_confirm": False}

print("\n--- invoking graph (will pause at confirm gate) ---")
result = graph.invoke(init, config)

if "__interrupt__" in result:
    payload = result["__interrupt__"][0].value
    metrics = payload["review_metrics"]
    flags = payload["flags"]
    print(f"⏸  PAUSED at confirm gate: {len(metrics)} extracted values, {len(flags)} validation flag(s).")
    print("   (analyst would review/edit here; simulating 'approve as-is')")
    # Resume: confirm the reviewed metrics as-is.
    final = graph.invoke(Command(resume=metrics), config)
else:
    final = result

op = final["onepager"]
print(f"\n--- COMPLETE ---")
print(f"company   : {op['company']}  ({op['period']})")
print(f"metrics   : {len(op['metrics'])}  | sentiment: {op['sentiment']}")
print(f"summary   : {op['summary'][:280]}…")
print(f"headwinds : {len(op['headwinds'])} | tailwinds: {len(op['tailwinds'])}")
print(f"dataQuality gaps: {op['dataQuality']['gaps']}")
