"""Dense embeddings via Nebius Token Factory (the course-required model call).

`embed_chunks` fills each chunk's .embedding in batches; `embed_query` embeds one string.
Kept thin on top of clients.embed_texts so the only Nebius-specific surface is one HTTP call.
"""
from __future__ import annotations

from ..clients import embed_texts
from ..config import settings
from .models import Chunk

BATCH = 64


def embed_chunks(chunks: list[Chunk], batch: int = BATCH) -> list[Chunk]:
    """Embed chunk.content in batches; sets chunk.embedding in place. Returns the list."""
    for i in range(0, len(chunks), batch):
        window = chunks[i:i + batch]
        vecs = embed_texts([c.content for c in window])
        for c, v in zip(window, vecs):
            c.embedding = v
            _check_dim(v)
    return chunks


def embed_query(text: str) -> list[float]:
    vec = embed_texts([text])[0]
    _check_dim(vec)
    return vec


def _check_dim(vec: list[float]) -> None:
    """Guard: embedding dim must match the configured pgvector column dimension."""
    if len(vec) != settings.nebius_embed_dim:
        raise ValueError(
            f"Embedding dim {len(vec)} != NEBIUS_EMBED_DIM={settings.nebius_embed_dim}. "
            f"Update NEBIUS_EMBED_DIM and the vector() column in db/0001_rag_tables.sql to match "
            f"the '{settings.nebius_embed_model}' model."
        )
