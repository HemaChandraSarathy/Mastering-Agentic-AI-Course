"""Assemble a CompanyInsightData one-pager (a portfolio-company insights view).

Numbers come from Pipeline A (deterministic + confirmed). Narrative fields (summary,
sentiment, headwinds, tailwinds, recommendations) are filled later by Pipeline B; here
they default to empty so the structure renders before the RAG path is wired.

INTEGRITY: latestMark / exitReadiness are None unless that data actually exists in the
corpus — we never fabricate a valuation mark or exit score. `recommendations` stays empty
(aggregation-first; no synthesis).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

from .pipeline_a.models import ExtractedMetric, ValidationFlag, VarianceRow, period_sort_key
from .taxonomy import ALL_METRICS, Unit

Flag = Literal["ok", "warning", "alert"]


class InsightMetric(BaseModel):
    name: str
    value: str
    qoq: str
    yoy: str
    flag: Flag
    note: Optional[str] = None
    provenance: Optional[str] = None     # source cell, e.g. 'Income Statement!E11'
    confidence: Optional[float] = None   # extraction confidence 0..1
    recency: Optional[str] = None        # period the figure is as-of (e.g. 'Q3 2025')


class InsightDataSource(BaseModel):
    name: str
    type: Literal["document", "session"]
    date: Optional[str] = None
    metrics: int = 0
    status: Literal["current", "missing"]


class CompanyInsightData(BaseModel):
    company: str
    sector: str
    period: str
    generatedAt: str
    note: Optional[str] = None          # e.g. a sample-data disclaimer; shown as a banner if set

    latestMark: Optional[dict] = None
    exitReadiness: Optional[dict] = None
    dataQuality: dict

    summary: str = ""
    sentiment: Literal["positive", "negative", "neutral", "mixed"] = "neutral"
    metrics: list[InsightMetric] = []
    headwinds: list[str] = []
    tailwinds: list[str] = []
    painPoints: list[str] = []
    dataSources: list[InsightDataSource] = []
    recommendations: list = []           # deferred synthesis hook — stays empty


def _fmt_value(metric_type: str, value: float) -> str:
    unit = ALL_METRICS[metric_type].unit if metric_type in ALL_METRICS else None
    if unit == Unit.USD_M:
        return f"${value:,.0f}M"
    if unit == Unit.PCT:
        return f"{value:.1f}%"
    if unit == Unit.MULTIPLE:
        return f"{value:.1f}x"
    if unit == Unit.COUNT:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _fmt_pct(p: Optional[float]) -> str:
    return f"{p*100:+.1f}%" if p is not None else "—"


def assemble(
    metrics: list[ExtractedMetric],
    flags: list[ValidationFlag],
    variance: list[VarianceRow],
    *,
    company: str = "Company",
    sector: str = "",
    corpus_files: Optional[list[str]] = None,
    docs_expected: int = 10,
    generated_at: Optional[str] = None,
    narrative: Optional[dict] = None,   # {summary, sentiment, headwinds[], tailwinds[]} from Pipeline B
    note: Optional[str] = None,         # optional banner (e.g. sample-data disclaimer)
) -> CompanyInsightData:
    mapped = [m for m in metrics if m.metric_type is not None]
    periods = sorted({m.period for m in mapped}, key=period_sort_key)
    latest = periods[-1] if periods else ""

    # index variance by (metric_type, period) for qoq lookup
    var_idx = {(v.metric_type, v.period): v for v in variance}
    # index flags by (metric_type, period) for the worst severity
    sev_rank = {"error": 3, "warning": 2, "info": 1}
    worst: dict[tuple, str] = {}
    for f in flags:
        if f.metric_type and f.period:
            key = (f.metric_type, f.period)
            if sev_rank.get(f.severity, 0) > sev_rank.get(worst.get(key, ""), 0):
                worst[key] = f.severity

    insight_metrics: list[InsightMetric] = []
    for m in sorted({mm.metric_type for mm in mapped if mm.period == latest}):
        cur = next(x for x in mapped if x.metric_type == m and x.period == latest)
        v = var_idx.get((m, latest))
        # flag: validation error -> alert; warning or variance-flag -> warning; else ok
        sev = worst.get((m, latest))
        if sev == "error":
            flag: Flag = "alert"
        elif sev == "warning" or sev == "info" or (v and v.flagged):
            flag = "warning"
        else:
            flag = "ok"
        insight_metrics.append(InsightMetric(
            name=ALL_METRICS[m].label,
            value=_fmt_value(m, cur.value),
            qoq=_fmt_pct(v.qoq_pct) if v else "—",
            yoy="—",  # YoY needs same-quarter prior-year; available later
            flag=flag,
            provenance=(cur.cell_ref if (cur.cell_ref and "!" in cur.cell_ref)
                        else (f"{cur.tab}!{cur.cell_ref}" if cur.cell_ref else cur.source_file)),
            confidence=cur.confidence,
            recency=cur.period,
        ))

    files = corpus_files or []
    data_sources = [
        InsightDataSource(name=f, type="document", date=None,
                          metrics=sum(1 for m in mapped if m.source_file == f),
                          status="current")
        for f in files
    ]
    gaps = []
    if not any(m.metric_type == "ebitda" for m in mapped):
        gaps.append("EBITDA not reported in source")
    if not any(m.metric_type in ("net_debt", "cash") for m in mapped):
        gaps.append("Balance-sheet metrics (cash, net debt) not in source")

    n = narrative or {}
    return CompanyInsightData(
        company=company,
        sector=sector,
        period=latest,
        generatedAt=generated_at or datetime.now().strftime("%Y-%m-%d %H:%M"),
        note=note,
        latestMark=None,            # no valuation mark in corpus — do not fabricate
        exitReadiness=None,         # no exit data in corpus — do not fabricate
        dataQuality={
            "docsAvailable": len(files),
            "docsExpected": docs_expected,
            "lastUpdated": latest,
            "gaps": gaps,
        },
        metrics=insight_metrics,
        dataSources=data_sources,
        summary=n.get("summary", ""),
        sentiment=n.get("sentiment", "neutral"),
        headwinds=n.get("headwinds", []),
        tailwinds=n.get("tailwinds", []),
    )
