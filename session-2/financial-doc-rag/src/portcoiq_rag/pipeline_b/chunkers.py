"""Two chunking strategies, compared in eval (course requirement):

  - fixed_chunks: fixed ~N-token windows with overlap. Simple, ignores structure.
  - structural_chunks: split on document structure (transcript speaker turns / section
    headers; analyst-report headings), then pack to a token budget. Keeps semantically
    coherent units together.

Both preserve page provenance.
"""
from __future__ import annotations

import re

import numpy as np

from .loaders import LoadedDoc
from .models import Chunk

WORDS_PER_TOKEN = 1 / 1.3   # inverse of the ~1.3 tokens/word estimate


def _target_words(target_tokens: int) -> int:
    return max(1, int(target_tokens * WORDS_PER_TOKEN))


# ---------------------------------------------------------------------------
# Fixed-size
# ---------------------------------------------------------------------------
def fixed_chunks(doc: LoadedDoc, target_tokens: int = 1000, overlap_tokens: int = 150) -> list[Chunk]:
    words_pages: list[tuple[str, int]] = [
        (w, page) for page, text in doc.pages for w in text.split()
    ]
    if not words_pages:
        return []
    size = _target_words(target_tokens)
    step = max(1, size - _target_words(overlap_tokens))

    chunks: list[Chunk] = []
    idx = 0
    for start in range(0, len(words_pages), step):
        window = words_pages[start:start + size]
        if not window:
            break
        content = " ".join(w for w, _ in window)
        chunks.append(Chunk(
            content=content, company=doc.company, doc_type=doc.doc_type, period=doc.period,
            source_file=doc.source_file, page=window[0][1], strategy="fixed", chunk_index=idx,
        ))
        idx += 1
        if start + size >= len(words_pages):
            break
    return chunks


# ---------------------------------------------------------------------------
# Structure-aware
# ---------------------------------------------------------------------------
_SECTION_HEADERS = {
    "corporate participants", "conference call participants", "presentation",
    "questions and answers", "q&a", "operator", "rating", "highlights",
    "analysis", "investment thesis", "financial & risk analysis", "valuation",
    "earnings & growth analysis", "risks",
}
# transcript speaker turn: "Ryan Lance ConocoPhillips - Chairman ..." / "... - Analyst"
_SPEAKER_RE = re.compile(r"^[A-Z][A-Za-z.''-]+(?: [A-Z][A-Za-z.''-]+){1,3}\s+.+\s-\s+[A-Z]")


def _is_boundary(line: str, doc_type: str | None) -> str | None:
    """Return a section label if `line` starts a new structural unit, else None."""
    s = line.strip()
    if not s:
        return None
    low = s.lower().rstrip(":")
    if low in _SECTION_HEADERS:
        return s
    if doc_type == "earnings_transcript" and len(s) < 120 and _SPEAKER_RE.match(s):
        return s
    # analyst-report heading: short, mostly uppercase letters
    letters = [c for c in s if c.isalpha()]
    if doc_type == "analyst_report" and 2 <= len(s) <= 60 and letters and \
            sum(c.isupper() for c in letters) / len(letters) > 0.8:
        return s
    return None


def structural_chunks(doc: LoadedDoc, target_tokens: int = 1000) -> list[Chunk]:
    target = _target_words(target_tokens)
    # don't emit fragments smaller than this — absorb headers/short turns into the chunk.
    min_words = max(40, target // 5)
    chunks: list[Chunk] = []
    idx = 0
    cur_words: list[str] = []
    cur_page: int | None = None
    cur_section: str | None = None

    def flush():
        nonlocal cur_words, idx
        if cur_words:
            chunks.append(Chunk(
                content=" ".join(cur_words), company=doc.company, doc_type=doc.doc_type,
                period=doc.period, source_file=doc.source_file, page=cur_page,
                strategy="structural", chunk_index=idx, section=cur_section,
            ))
            idx += 1
            cur_words = []

    for page, text in doc.pages:
        for line in text.splitlines():
            words = line.split()
            if not words:
                continue
            boundary = _is_boundary(line, doc.doc_type)
            # Start a new chunk at a boundary ONLY if the current one is substantial,
            # or when we've hit the size target. Otherwise absorb (just update section).
            if (boundary and len(cur_words) >= min_words) or len(cur_words) >= target:
                flush()
            if boundary:
                cur_section = boundary
            if not cur_words:
                cur_page = page
            cur_words.extend(words)
    flush()
    return chunks


# ---------------------------------------------------------------------------
# Semantic (embedding-based) — like LangChain's SemanticChunker
# ---------------------------------------------------------------------------
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _mk_chunk(sents, doc, idx, strategy):
    return Chunk(content=" ".join(s for s, _ in sents), company=doc.company, doc_type=doc.doc_type,
                 period=doc.period, source_file=doc.source_file, page=sents[0][1],
                 strategy=strategy, chunk_index=idx)


def semantic_chunks(doc: LoadedDoc, threshold_percentile: int = 70,
                    max_tokens: int = 400) -> list[Chunk]:
    """Embed each sentence, place a chunk boundary where adjacent-sentence cosine distance spikes
    above the Nth percentile (a topic shift). Keeps semantically-coherent passages together.
    Requires the Nebius embedder (network)."""
    from ..clients import embed_texts

    sents: list[tuple[str, int]] = []
    for page, text in doc.pages:
        for s in _SENT_SPLIT.split(text):
            s = s.strip()
            if s:
                sents.append((s, page))
    if len(sents) <= 1:
        return [_mk_chunk(sents, doc, 0, "semantic")] if sents else []

    vecs = np.asarray(embed_texts([s for s, _ in sents]), dtype=np.float32)
    vecs /= (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
    dists = 1.0 - np.sum(vecs[:-1] * vecs[1:], axis=1)   # adjacent cosine distance
    thr = float(np.percentile(dists, threshold_percentile))
    target_words = int(max_tokens * WORDS_PER_TOKEN)

    chunks, cur, idx = [], [sents[0]], 0
    for i in range(1, len(sents)):
        cur_words = sum(len(s.split()) for s, _ in cur)
        if dists[i - 1] > thr or cur_words >= target_words:
            chunks.append(_mk_chunk(cur, doc, idx, "semantic"))
            idx += 1
            cur = []
        cur.append(sents[i])
    if cur:
        chunks.append(_mk_chunk(cur, doc, idx, "semantic"))
    return chunks


def chunk_doc(doc: LoadedDoc, strategy: str, **kw) -> list[Chunk]:
    if strategy == "fixed":
        return fixed_chunks(doc, **kw)
    if strategy == "semantic":
        return semantic_chunks(doc, **kw)
    return structural_chunks(doc, **kw)
