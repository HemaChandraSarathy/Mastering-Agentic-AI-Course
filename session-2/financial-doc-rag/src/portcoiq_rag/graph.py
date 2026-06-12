"""LangGraph orchestration of the full RAG pipeline.

    extract → validate → variance → [CONFIRM GATE] → generate_brief → assemble

The confirm gate is a real human-in-the-loop pause (LangGraph `interrupt`): the graph stops
with the extracted metrics for the analyst to review, then resumes with the confirmed set.
Set auto_confirm=True to skip the pause (headless runs / eval).

State holds only JSON-serializable values (dicts), so it checkpoints cleanly across the
interrupt. The retriever is injected via closure (not state), so heavy/non-serializable
objects never enter the checkpoint.
"""
from __future__ import annotations

from typing import Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from . import onepager
from .pipeline_a.extract import extract_from_excel
from .pipeline_a.models import ExtractedMetric, VarianceRow, ValidationFlag, period_sort_key
from .pipeline_a.validate import validate
from .pipeline_a.variance import compute_variance
from .pipeline_b import generate
from .taxonomy import ALL_METRICS


class PipelineState(TypedDict, total=False):
    xlsx_path: str
    corpus_files: list
    auto_confirm: bool
    metrics: list            # list[dict] of ExtractedMetric
    flags: list              # list[dict] of ValidationFlag
    variance: list           # list[dict] of VarianceRow
    confirmed_metrics: list  # list[dict] after the gate
    question: str
    narrative: dict
    onepager: dict           # CompanyInsightData dict


def _extract(state: PipelineState) -> dict:
    metrics = extract_from_excel(state["xlsx_path"])
    return {"metrics": [m.model_dump() for m in metrics]}


def _validate(state: PipelineState) -> dict:
    metrics = [ExtractedMetric(**d) for d in state["metrics"]]
    return {"flags": [f.model_dump() for f in validate(metrics)]}


def _variance(state: PipelineState) -> dict:
    metrics = [ExtractedMetric(**d) for d in state["metrics"]]
    return {"variance": [v.model_dump() for v in compute_variance(metrics)]}


def _confirm_gate(state: PipelineState) -> dict:
    """Human-in-the-loop. Pauses for review unless auto_confirm is set."""
    if state.get("auto_confirm"):
        return {"confirmed_metrics": state["metrics"]}
    # Pause: hand the extracted metrics + flags out for analyst review.
    decision = interrupt({"review_metrics": state["metrics"], "flags": state.get("flags", [])})
    # Resume value may be the confirmed metric list, or anything truthy = "approve as-is".
    confirmed = decision if isinstance(decision, list) else state["metrics"]
    return {"confirmed_metrics": confirmed}


def _make_generate(retriever):
    def _generate_brief(state: PipelineState) -> dict:
        if retriever is None:
            return {"narrative": {}}  # numbers-only one-pager
        metrics = [ExtractedMetric(**d) for d in state["confirmed_metrics"] if d.get("metric_type")]
        if not metrics:
            return {"narrative": {}}
        latest = sorted({m.period for m in metrics}, key=period_sort_key)[-1]
        var = [VarianceRow(**v) for v in state.get("variance", [])]
        mlines = [f"{ALL_METRICS[m.metric_type].label}: {m.value:,.0f} {m.unit or ''}".strip()
                  for m in metrics if m.period == latest]
        vlines = [f"{ALL_METRICS[v.metric_type].label}: {v.qoq_pct*100:+.1f}% QoQ"
                  for v in var if v.period == latest and v.qoq_pct is not None]
        q = f"What changed for ConocoPhillips in {latest} and why?"
        hits = generate.rerank(q, retriever.search(q, k=8), top_n=4)
        return {"question": q, "narrative": generate.generate_narrative(mlines, vlines, hits)}
    return _generate_brief


def _assemble(state: PipelineState) -> dict:
    metrics = [ExtractedMetric(**d) for d in state["confirmed_metrics"]]
    flags = [ValidationFlag(**f) for f in state.get("flags", [])]
    variance = compute_variance(metrics)
    insight = onepager.assemble(metrics, flags, variance,
                                corpus_files=state.get("corpus_files"),
                                narrative=state.get("narrative") or None)
    return {"onepager": insight.model_dump()}


def build_graph(retriever=None):
    """Compile the pipeline graph. Pass a retriever to enable the narrative step."""
    g = StateGraph(PipelineState)
    g.add_node("extract", _extract)
    g.add_node("validate", _validate)
    g.add_node("variance", _variance)
    g.add_node("confirm_gate", _confirm_gate)
    g.add_node("generate_brief", _make_generate(retriever))
    g.add_node("assemble", _assemble)

    g.add_edge(START, "extract")
    g.add_edge("extract", "validate")
    g.add_edge("validate", "variance")
    g.add_edge("variance", "confirm_gate")
    g.add_edge("confirm_gate", "generate_brief")
    g.add_edge("generate_brief", "assemble")
    g.add_edge("assemble", END)

    return g.compile(checkpointer=MemorySaver())
