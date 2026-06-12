"""Retrieval over narrative chunks.

Now (keyless): BM25 sparse retrieval (rank-bm25). Wired but inactive until keys: dense
(Nebius embeddings + pgvector) and an LLM reranker. `hybrid_search` fuses sparse + dense
ranks via Reciprocal Rank Fusion; with dense absent it degrades gracefully to sparse-only.

Refusal-first: `search` returns (chunk, score) pairs; a low top score signals "not found
in this company's documents" rather than forcing a fabricated answer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi

from .models import Chunk

_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are", "was", "were",
    "be", "as", "at", "by", "with", "that", "this", "it", "its", "what", "how", "did", "do",
    "does", "from", "vs", "about",
}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP and len(t) > 1]


@dataclass
class Hit:
    chunk: Chunk
    score: float


class BM25Retriever:
    """Sparse lexical retrieval — no keys, no model. Good baseline + exact-match recall."""

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self._tokens = [tokenize(c.content) for c in chunks]
        self._bm25 = BM25Okapi(self._tokens) if chunks else None

    def search(self, query: str, k: int = 8) -> list[Hit]:
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(zip(self.chunks, scores), key=lambda x: x[1], reverse=True)
        return [Hit(chunk=c, score=float(s)) for c, s in ranked[:k]]


class InMemoryDenseRetriever:
    """Dense semantic retrieval over in-memory chunk embeddings (cosine similarity).

    Used for the demo/eval before Supabase pgvector persistence is wired — same vectors,
    same Nebius model, just held in a numpy matrix instead of the DB. Chunks must already
    have .embedding set (see embed.embed_chunks).
    """

    def __init__(self, chunks: list[Chunk]):
        self.chunks = [c for c in chunks if c.embedding is not None]
        if self.chunks:
            mat = np.asarray([c.embedding for c in self.chunks], dtype=np.float32)
            self._mat = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
        else:
            self._mat = np.zeros((0, 0), dtype=np.float32)

    def search(self, query: str, k: int = 8) -> list[Hit]:
        if not self.chunks:
            return []
        from .embed import embed_query
        q = np.asarray(embed_query(query), dtype=np.float32)
        q /= (np.linalg.norm(q) + 1e-9)
        sims = self._mat @ q
        idx = np.argsort(-sims)[:k]
        return [Hit(chunk=self.chunks[i], score=float(sims[i])) for i in idx]


_FLASHRANK = None


def _flashrank_ranker():
    global _FLASHRANK
    if _FLASHRANK is None:
        from flashrank import Ranker
        _FLASHRANK = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="_scratch/flashrank")
    return _FLASHRANK


def flashrank_rerank(query: str, hits: list[Hit], top_n: int = 3) -> list[Hit]:
    """Cross-encoder rerank via FlashRank (onnxruntime, no torch). Returns top_n with CALIBRATED
    relevance scores (0..1) — useful both for ordering and as a refusal signal."""
    if not hits:
        return []
    from flashrank import RerankRequest
    ranker = _flashrank_ranker()
    passages = [{"id": i, "text": h.chunk.content} for i, h in enumerate(hits)]
    results = ranker.rerank(RerankRequest(query=query, passages=passages))
    return [Hit(chunk=hits[r["id"]].chunk, score=float(r["score"])) for r in results[:top_n]]


def reciprocal_rank_fusion(rank_lists: list[list[Chunk]], k: int = 60) -> list[Chunk]:
    """Fuse multiple ranked lists (RRF). Used by hybrid once dense retrieval is on."""
    scores: dict[int, float] = {}
    ref: dict[int, Chunk] = {}
    for lst in rank_lists:
        for rank, ch in enumerate(lst):
            key = id(ch)
            ref[key] = ch
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [ref[key] for key, _ in ordered]


def extract_query_period(query: str):
    """If the query names a quarter (e.g. 'Q3 2025'), return canonical 'Qn YYYY', else None."""
    from ..pipeline_a.models import parse_period
    return parse_period(query)


def _period_ok(chunk: Chunk, period: str | None) -> bool:
    # keep chunks of the asked period; undated docs (analyst reports) are always eligible.
    return period is None or chunk.period == period or chunk.period is None


class HybridRetriever:
    """Sparse + (optional) dense, fused with RRF, with optional period metadata filtering.

    Dense activates when an embedder is passed. When the query names a quarter, results are
    restricted to that period's chunks (+ undated docs) — this deterministically fixes the
    'Q3 vs Q4' confusion that neither lexical nor dense ranking fully solves on its own.
    """

    def __init__(self, chunks: list[Chunk], dense=None):
        self.chunks = chunks
        self.sparse = BM25Retriever(chunks)
        self.dense = dense   # object with .search(query, k) -> list[Hit]; None until embedder

    def search(self, query: str, k: int = 8, min_score: float = 1.0) -> list[Hit]:
        period = extract_query_period(query)
        pool = k * 4  # retrieve wide, then period-filter, then take k
        sparse_hits = [h for h in self.sparse.search(query, k=pool) if _period_ok(h.chunk, period)]
        if self.dense is None:
            if not sparse_hits or sparse_hits[0].score < min_score:
                return []
            return sparse_hits[:k]
        dense_hits = [h for h in self.dense.search(query, k=pool) if _period_ok(h.chunk, period)]
        fused = reciprocal_rank_fusion(
            [[h.chunk for h in sparse_hits], [h.chunk for h in dense_hits]]
        )
        return [Hit(chunk=c, score=1.0 / (i + 1)) for i, c in enumerate(fused[:k])]
