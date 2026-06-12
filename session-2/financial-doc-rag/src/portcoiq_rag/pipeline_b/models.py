"""Models for the narrative RAG pipeline."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """One retrievable narrative chunk with provenance metadata."""
    content: str
    company: Optional[str] = None
    doc_type: Optional[str] = None          # earnings_transcript | analyst_report | news_release
    period: Optional[str] = None            # canonical 'Qn YYYY' if known
    source_file: str = ""
    page: Optional[int] = None
    strategy: str = "fixed"                  # 'fixed' | 'structural'
    chunk_index: int = 0
    section: Optional[str] = None            # structure-aware section label, if any
    embedding: Optional[list[float]] = Field(default=None, exclude=True)

    @property
    def approx_tokens(self) -> int:
        # ~1.3 tokens per whitespace word — good enough for sizing without tiktoken.
        return int(len(self.content.split()) * 1.3)

    def metadata(self) -> dict:
        return {
            "company": self.company,
            "doc_type": self.doc_type,
            "period": self.period,
            "source_file": self.source_file,
            "page": self.page,
            "strategy": self.strategy,
            "chunk_index": self.chunk_index,
            "section": self.section,
        }
