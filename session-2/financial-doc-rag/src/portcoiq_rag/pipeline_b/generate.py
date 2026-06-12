"""Generation via Claude: LLM rerank, grounded cited Q&A (with refusal), and the one-pager
narrative. All generation is constrained to the retrieved sources + confirmed Pipeline A
numbers — never outside knowledge, never invented figures (metrics-integrity rule).
"""
from __future__ import annotations

import json
import re

from ..clients import anthropic_client
from ..config import settings
from .retrieve import Hit

try:  # tidy, named spans in LangSmith; no-op if langsmith is unavailable.
    from langsmith import traceable
except Exception:  # pragma: no cover
    def traceable(*_a, **_k):
        def _deco(f):
            return f
        return _deco

REFUSAL = "Not found in this company's documents."


def _summ_hits(hits) -> list[dict]:
    """Lightweight source summary for traces — no embeddings, truncated content."""
    return [{"src": h.chunk.source_file, "page": h.chunk.page,
             "section": h.chunk.section, "preview": (h.chunk.content or "")[:160]}
            for h in (hits or [])]


def _format_sources(hits: list[Hit], max_chars: int = 1200) -> str:
    out = []
    for i, h in enumerate(hits, 1):
        c = h.chunk
        loc = f"{c.source_file} p{c.page}" + (f" · {c.section}" if c.section else "")
        out.append(f"[S{i}] ({loc})\n{c.content[:max_chars]}")
    return "\n\n".join(out)


def _msg(system: str, user: str, max_tokens: int) -> str:
    r = anthropic_client().messages.create(
        model=settings.anthropic_model, max_tokens=max_tokens,
        system=system, messages=[{"role": "user", "content": user}],
    )
    return r.content[0].text.strip()


@traceable(run_type="chain", name="rerank",
           process_inputs=lambda i: {"query": i.get("query"), "candidates": len(i.get("hits") or [])},
           process_outputs=lambda o: {"reranked": len(o or [])})
def rerank(query: str, hits: list[Hit], top_n: int = 4) -> list[Hit]:
    """LLM reranker (cross-encoder needs torch / no 3.14 wheel). Returns top_n reordered."""
    if len(hits) <= top_n:
        return hits
    items = "\n".join(f"[{i}] {h.chunk.content[:300]}" for i, h in enumerate(hits))
    system = ("Rank the passages by relevance to the query. "
              "Return ONLY a JSON array of passage indices, best first, e.g. [3,0,5,1].")
    txt = _msg(system, f"Query: {query}\n\nPassages:\n{items}", max_tokens=120)
    m = re.search(r"\[[\d,\s]+\]", txt)
    order = json.loads(m.group(0)) if m else list(range(len(hits)))
    seen, ranked = set(), []
    for i in order:
        if isinstance(i, int) and 0 <= i < len(hits) and i not in seen:
            ranked.append(hits[i]); seen.add(i)
    for i in range(len(hits)):
        if i not in seen:
            ranked.append(hits[i])
    return ranked[:top_n]


@traceable(run_type="chain", name="answer_question",
           process_inputs=lambda i: {"question": i.get("question"), "sources": _summ_hits(i.get("hits"))})
def answer_question(question: str, hits: list[Hit], max_tokens: int = 600) -> str:
    """Grounded cited Q&A. Refuses when the answer isn't in the retrieved sources."""
    if not hits:
        return REFUSAL
    system = (
        "You are a PE analyst assistant. Answer ONLY using the provided sources. "
        "Cite every factual claim with [S#]. Use no outside knowledge and invent no numbers. "
        f"If the sources do not contain the answer, reply EXACTLY: '{REFUSAL}' "
        "Be direct and factual; no flattery, no hedging."
    )
    user = f"Question: {question}\n\nSources:\n{_format_sources(hits)}"
    return _msg(system, user, max_tokens)


@traceable(run_type="chain", name="qa", process_inputs=lambda i: {"question": i.get("question")})
def ask(question: str, retriever, k: int = 8, top_n: int = 4, min_score: float = 0.05) -> str:
    """Grouped Q&A span: retrieve → FlashRank rerank → cited answer/refusal.

    FlashRank's calibrated score gives a cheap first-line refusal: if even the top reranked
    passage scores below `min_score`, refuse without spending a Claude call. Otherwise Claude
    answers (and can still refuse) grounded in the reranked context.
    """
    from .retrieve import flashrank_rerank
    hits = flashrank_rerank(question, retriever.search(question, k=k), top_n=top_n)
    if not hits or hits[0].score < min_score:
        return REFUSAL
    return answer_question(question, hits)


_NARRATIVE_SYSTEM = (
    "You are a PE analyst's institutional-memory assistant. Write a CONCISE first-draft "
    "'what changed and why' for the company's latest quarter.\n"
    "RULES:\n"
    "- Use ONLY the confirmed metrics provided for any figure. Never invent or recompute numbers.\n"
    "- Ground every qualitative claim in the narrative sources and cite with [S#].\n"
    "- Aggregation-first: describe what changed and the stated reasons; do NOT prescribe actions "
    "or speculate on causation beyond the sources.\n"
    "- Direct, factual tone — no flattery.\n"
    "LENGTH LIMITS: summary = 4-6 sentences; at most 4 headwinds and 4 tailwinds, one line each.\n"
    "Return ONLY valid JSON (no markdown, no code fence): "
    "{\"summary\": str, \"sentiment\": \"positive|negative|neutral|mixed\", "
    "\"headwinds\": [str], \"tailwinds\": [str]}"
)


def _parse_json(txt: str) -> dict | None:
    s = txt.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)   # strip code fences
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


@traceable(run_type="chain", name="faithfulness_judge",
           process_inputs=lambda i: {"answer_preview": (i.get("answer") or "")[:200],
                                      "sources": _summ_hits(i.get("hits"))})
def judge_faithfulness(answer: str, hits: list[Hit]) -> float:
    """LLM-judge (RAGAS-style): fraction of the answer's claims supported by the sources, 0..1.

    Custom (not the `ragas` package) to avoid langchain-version / Python-3.14 conflicts.
    Counts claims explicitly (supported / total) rather than asking for a bare number —
    a bare-number judge proved noisy and under-scored fully-grounded answers.
    """
    if not hits:
        return 0.0
    system = (
        "You evaluate FAITHFULNESS of an ANSWER against its SOURCES. Steps:\n"
        "1. List each distinct factual claim in the ANSWER.\n"
        "2. For each, decide if the SOURCES support it (ignore [S#] citation markers themselves).\n"
        "   Be reasonable: a claim is supported if the sources clearly back it.\n"
        "3. End with a final line exactly: 'SCORE: <supported>/<total>'.\n"
        "Refusals ('not found...') with no claims score SCORE: 1/1."
    )
    user = f"SOURCES:\n{_format_sources(hits)}\n\nANSWER:\n{answer}"
    txt = _msg(system, user, max_tokens=700)
    m = re.search(r"SCORE:\s*(\d+)\s*/\s*(\d+)", txt)
    if not m:
        return 0.0
    supported, total = int(m.group(1)), int(m.group(2))
    return supported / total if total else 0.0


@traceable(run_type="chain", name="context_precision",
           process_inputs=lambda i: {"question": i.get("question"), "k": len(i.get("hits") or [])})
def judge_context_precision(question: str, hits: list[Hit], reference: str) -> float:
    """RAGAS-style context precision@k: are the relevant chunks ranked near the top? 0..1."""
    if not hits:
        return 0.0
    items = "\n".join(f"[{i}] {h.chunk.content[:500]}" for i, h in enumerate(hits))
    system = ("Given a QUESTION, its reference ANSWER, and retrieved PASSAGES, output ONLY a JSON array "
              "of 0/1 flags — one per passage, in order — where 1 means the passage is relevant to "
              "answering the question. Example: [1,0,1]")
    txt = _msg(system, f"QUESTION: {question}\nANSWER: {reference}\n\nPASSAGES:\n{items}", max_tokens=60)
    m = re.search(r"\[[01,\s]+\]", txt)
    try:
        flags = json.loads(m.group(0)) if m else [0] * len(hits)
    except json.JSONDecodeError:
        flags = [0] * len(hits)
    flags = (list(flags) + [0] * len(hits))[:len(hits)]
    total_rel = sum(flags)
    if total_rel == 0:
        return 0.0
    cum, acc = 0, 0.0
    for k, rel in enumerate(flags, 1):
        if rel:
            cum += 1
            acc += cum / k          # precision@k at each relevant hit
    return acc / total_rel


@traceable(run_type="chain", name="context_recall",
           process_inputs=lambda i: {"k": len(i.get("hits") or [])})
def judge_context_recall(reference: str, hits: list[Hit]) -> float:
    """RAGAS-style context recall: is the reference answer supported by the retrieved context? 0..1."""
    if not hits:
        return 0.0
    system = ("Given a reference ANSWER and retrieved CONTEXT, break the answer into factual claims, "
              "mark each as supported or not supported by the context, then end with a final line "
              "exactly: 'SCORE: <supported>/<total>'.")
    txt = _msg(system, f"CONTEXT:\n{_format_sources(hits)}\n\nANSWER:\n{reference}", max_tokens=500)
    m = re.search(r"SCORE:\s*(\d+)\s*/\s*(\d+)", txt)
    if not m:
        return 0.0
    s, t = int(m.group(1)), int(m.group(2))
    return s / t if t else 0.0


@traceable(run_type="chain", name="generate_narrative",
           process_inputs=lambda i: {"metric_lines": i.get("metric_lines"),
                                      "variance_lines": i.get("variance_lines"),
                                      "sources": _summ_hits(i.get("hits"))})
def generate_narrative(metric_lines: list[str], variance_lines: list[str],
                       hits: list[Hit], max_tokens: int = 1600) -> dict:
    """Produce the one-pager narrative (summary/sentiment/headwinds/tailwinds), cited + grounded."""
    user = (
        f"Confirmed metrics (latest period):\n" + "\n".join(metric_lines) +
        f"\n\nVariance vs prior period:\n" + "\n".join(variance_lines) +
        f"\n\nNarrative sources:\n{_format_sources(hits)}\n\nReturn the JSON."
    )
    txt = _msg(_NARRATIVE_SYSTEM, user, max_tokens)
    parsed = _parse_json(txt)
    if parsed is None:
        return {"summary": txt, "sentiment": "neutral", "headwinds": [], "tailwinds": []}
    parsed.setdefault("sentiment", "neutral")
    parsed.setdefault("headwinds", [])
    parsed.setdefault("tailwinds", [])
    return parsed
