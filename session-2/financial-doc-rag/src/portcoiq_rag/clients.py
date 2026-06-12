"""Lazy client constructors for Nebius (embeddings), Anthropic (generation), Supabase.

Clients are created on first use so that importing modules (e.g. for the taxonomy or
synthetic-Excel script) never requires secrets to be present.
"""
from __future__ import annotations

import os
from functools import lru_cache

from .config import settings


@lru_cache(maxsize=1)
def nebius_embeddings_client():
    """OpenAI-compatible client pointed at Nebius Token Factory (embeddings).

    Course requirement: at least one model call goes through Nebius — that's this one.
    """
    from openai import OpenAI

    settings.require_nebius()
    return OpenAI(api_key=settings.nebius_api_key, base_url=settings.nebius_base_url)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts via Nebius. Returns one vector per input.

    Requests `dimensions=NEBIUS_EMBED_DIM` (Qwen3-Embedding supports Matryoshka truncation),
    so we get clean 1024-dim vectors that fit an indexed pgvector(1024) column instead of the
    native 4096. Query and chunk embeddings use the same dim, so similarity stays consistent.
    """
    client = nebius_embeddings_client()
    resp = client.embeddings.create(
        model=settings.nebius_embed_model,
        input=texts,
        dimensions=settings.nebius_embed_dim,
    )
    return [d.embedding for d in resp.data]


@lru_cache(maxsize=1)
def anthropic_client():
    """Anthropic client for generation (claude-sonnet-4-6).

    When LANGSMITH_TRACING=true, wrap with LangSmith so every Claude call (rerank, generate,
    answer, faithfulness) is captured as a span — nested under the LangGraph run when called
    from a node. No-op / safe when tracing is off or langsmith is unavailable.
    """
    import anthropic

    settings.require_anthropic()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    if os.getenv("LANGSMITH_TRACING", "").lower() == "true":
        try:
            from langsmith.wrappers import wrap_anthropic
            client = wrap_anthropic(client)
        except Exception:
            pass
    return client


@lru_cache(maxsize=1)
def supabase_client():
    """Supabase client (service role). Pins the host via DoH if the local resolver fails."""
    from urllib.parse import urlparse

    from supabase import create_client

    from ._dns import pin_host

    settings.require_supabase()
    host = urlparse(settings.supabase_url).hostname
    if host:
        pin_host(host)   # no-op if the OS resolver already works
    return create_client(settings.supabase_url, settings.supabase_service_key)
