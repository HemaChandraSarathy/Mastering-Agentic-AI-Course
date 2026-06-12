"""Pydantic models + period helpers for the deterministic numbers pipeline."""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel

_QUARTER_RE = re.compile(r"q\s*([1-4])\s*[-/_ ]?\s*(\d{4})", re.IGNORECASE)


def parse_period(raw: str) -> Optional[str]:
    """Normalize a messy period header to canonical 'Qn YYYY', or None.

    Handles 'Q3 2024', 'Q3-2024', 'q3/2024', 'Q32024'.
    """
    if not raw:
        return None
    m = _QUARTER_RE.search(str(raw).strip())
    if not m:
        return None
    return f"Q{m.group(1)} {m.group(2)}"


def period_sort_key(period: str) -> tuple[int, int]:
    """Chronological sort key for 'Qn YYYY' -> (year, quarter)."""
    m = _QUARTER_RE.search(period)
    if not m:
        return (0, 0)
    return (int(m.group(2)), int(m.group(1)))


class ExtractedMetric(BaseModel):
    """One value pulled deterministically from a source cell.

    `metric_type` is None when the raw label didn't map to the taxonomy — surfaced to the
    analyst at the confirm gate rather than dropped or force-fit.
    """
    raw_label: str
    metric_type: Optional[str]          # canonical metric_type, or None if unmapped
    period: str                          # canonical 'Qn YYYY'
    value: float
    unit: Optional[str] = None
    # provenance
    source_file: str
    tab: Optional[str] = None
    cell_ref: Optional[str] = None       # e.g. 'B7'
    confidence: Optional[float] = None   # extraction confidence 0..1 (transparency triad)
    confirmed: bool = False

    @property
    def mapped(self) -> bool:
        return self.metric_type is not None


class ValidationFlag(BaseModel):
    rule: str
    severity: str                        # 'error' | 'warning' | 'info'
    message: str
    metric_type: Optional[str] = None
    period: Optional[str] = None


class VarianceRow(BaseModel):
    metric_type: str
    period: str
    value: float
    prior_period: Optional[str] = None
    prior_value: Optional[float] = None
    qoq_abs: Optional[float] = None
    qoq_pct: Optional[float] = None
    flagged: bool = False                # |qoq_pct| >= threshold
