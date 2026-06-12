"""Validate the Nebius embedding API: key, model, and dimension.

Usage: python scripts/test_nebius.py
Embeds two short strings and checks that the returned dim matches NEBIUS_EMBED_DIM.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from portcoiq_rag.config import settings
from portcoiq_rag.clients import embed_texts

print(f"model      = {settings.nebius_embed_model}")
print(f"base_url   = {settings.nebius_base_url}")
print(f"configured dim = {settings.nebius_embed_dim}")

vecs = embed_texts(["ConocoPhillips third-quarter results", "net income and revenue"])
print(f"\nembedded {len(vecs)} texts; actual dim = {len(vecs[0])}")
if len(vecs[0]) == settings.nebius_embed_dim:
    print("OK — dim matches NEBIUS_EMBED_DIM. Ready to embed the corpus + apply the migration.")
else:
    print(f"MISMATCH — set NEBIUS_EMBED_DIM={len(vecs[0])} in .env and the vector() column in "
          f"db/0001_rag_tables.sql to vector({len(vecs[0])}).")
