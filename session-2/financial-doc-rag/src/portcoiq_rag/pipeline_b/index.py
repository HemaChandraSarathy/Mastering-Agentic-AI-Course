"""Build a ready-to-query hybrid retriever over the corpus, with on-disk embedding cache.

Shared by the scripts and the Streamlit app so embeddings are computed once (Nebius) and
reused. When Supabase persistence lands, this is the seam to swap the in-memory dense index
for a pgvector-backed one.
"""
from __future__ import annotations

import pickle
from pathlib import Path

from .loaders import load_corpus
from .chunkers import structural_chunks, fixed_chunks
from .embed import embed_chunks
from .retrieve import HybridRetriever, InMemoryDenseRetriever

NARRATIVE_DOC_TYPES = {"earnings_transcript", "analyst_report"}


def build_retriever(corpus_dir: str | Path, cache_path: str | Path,
                    strategy: str = "structural", with_dense: bool = True) -> HybridRetriever:
    docs = load_corpus(corpus_dir, doc_types=NARRATIVE_DOC_TYPES)
    chunker = structural_chunks if strategy == "structural" else fixed_chunks
    chunks = [c for d in docs for c in chunker(d)]

    cache_path = Path(cache_path)
    cache = pickle.loads(cache_path.read_bytes()) if cache_path.exists() else {}

    def key(c):
        return (strategy, c.source_file, c.chunk_index, len(c.content))

    if with_dense:
        need = [c for c in chunks if key(c) not in cache]
        if need:
            embed_chunks(need)
            for c in need:
                cache[key(c)] = c.embedding
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(pickle.dumps(cache))
        for c in chunks:
            c.embedding = cache[key(c)]

    dense = InMemoryDenseRetriever(chunks) if with_dense else None
    return HybridRetriever(chunks, dense=dense)


def build_supabase_retriever(company_id: str | None = None) -> HybridRetriever:
    """Hybrid retriever reading from Supabase, optionally scoped to one company: BM25 over that
    company's chunk text + dense search via the company-filtered pgvector RPC. company_id=None
    searches across all companies (portfolio). Empty retriever if nothing is ingested.
    """
    from .store import load_chunks, SupabaseDenseRetriever
    chunks = load_chunks(company_id)
    dense = SupabaseDenseRetriever(company_id) if chunks else None
    return HybridRetriever(chunks, dense=dense)
