"""Deterministic variance: period-over-period change for each mapped metric.

Variance threshold: >=10% QoQ surfaces a flag.
"""
from __future__ import annotations

from collections import defaultdict

from .models import ExtractedMetric, VarianceRow, period_sort_key

QOQ_FLAG_THRESHOLD = 0.10  # 10% QoQ surfaces a flag


def compute_variance(
    metrics: list[ExtractedMetric],
    threshold: float = QOQ_FLAG_THRESHOLD,
) -> list[VarianceRow]:
    """For each mapped metric_type, sort periods and compute change vs the prior period."""
    by_type: dict[str, list[ExtractedMetric]] = defaultdict(list)
    for m in metrics:
        if m.metric_type is not None:
            by_type[m.metric_type].append(m)

    rows: list[VarianceRow] = []
    for metric_type, items in by_type.items():
        # dedup to one value per period (first wins), then sort chronologically
        per_period: dict[str, ExtractedMetric] = {}
        for it in items:
            per_period.setdefault(it.period, it)
        ordered = sorted(per_period.values(), key=lambda m: period_sort_key(m.period))

        prior: ExtractedMetric | None = None
        for cur in ordered:
            row = VarianceRow(metric_type=metric_type, period=cur.period, value=cur.value)
            if prior is not None:
                row.prior_period = prior.period
                row.prior_value = prior.value
                row.qoq_abs = cur.value - prior.value
                if prior.value != 0:
                    row.qoq_pct = (cur.value - prior.value) / abs(prior.value)
                    row.flagged = abs(row.qoq_pct) >= threshold
            rows.append(row)
            prior = cur
    return rows
