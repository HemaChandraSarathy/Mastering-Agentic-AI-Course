"""Centralized config — loads .env once and exposes typed settings.

No secrets live here; everything is read from the environment. Import `settings`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]


def _req(name: str) -> str:
    """Fetch a required env var, with a clear error if missing."""
    val = os.getenv(name)
    if not val:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return val


@dataclass(frozen=True)
class Settings:
    # Nebius (embeddings; OpenAI-compatible)
    nebius_api_key: str = os.getenv("NEBIUS_API_KEY", "")
    nebius_base_url: str = os.getenv("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1")
    nebius_embed_model: str = os.getenv("NEBIUS_EMBED_MODEL", "BAAI/bge-en-icl")
    nebius_embed_dim: int = int(os.getenv("NEBIUS_EMBED_DIM", "4096"))

    # Anthropic (generation)
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    # Supabase (shared project)
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "")

    # Corpus
    corpus_dir: Path = Path(os.getenv("CORPUS_DIR", str(REPO_ROOT / "corpus")))

    def require_nebius(self) -> "Settings":
        _req("NEBIUS_API_KEY")
        return self

    def require_anthropic(self) -> "Settings":
        _req("ANTHROPIC_API_KEY")
        return self

    def require_supabase(self) -> "Settings":
        _req("SUPABASE_URL")
        _req("SUPABASE_SERVICE_KEY")
        return self


settings = Settings()
