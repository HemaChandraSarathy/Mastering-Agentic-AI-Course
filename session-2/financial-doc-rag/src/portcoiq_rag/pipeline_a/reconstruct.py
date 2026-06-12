"""Reconstruct table rows/columns from positioned OCR tokens (LiteParse) -> ExtractedMetric.

This is the missing step between LiteParse (which returns positioned text tokens, NOT a
grid) and the rest of Pipeline A (taxonomy map -> validate -> variance), which expects
`ExtractedMetric` rows exactly like `extract_from_excel` produces. With this in place an
**image-only PDF** flows through the SAME deterministic downstream as a messy Excel.

Geometry, not ML:
  1. cluster tokens into rows by y-coordinate
  2. find the column-anchor row = the row whose tokens are period markers (a 4-digit year
     or a 'Qn YYYY'); each marker's x-center becomes a value-column anchor
  3. infer each column's canonical period by reading the stacked header above the anchor
     (e.g. 'Three Months Ended' + 'September 30' + '2025' -> 'Q3 2025'; 'Nine Months' -> '9M 2025')
  4. for each data row: left tokens = label; numeric tokens snap to the nearest column anchor
  5. map label -> taxonomy, emit one ExtractedMetric per (column, value) with bbox provenance
     and the token's OCR confidence

Determinism: no LLM. Same tokens -> same rows. Unmapped labels stay metric_type=None and
surface at the confirm gate (never force-fit), same contract as the Excel path.
"""
from __future__ import annotations

import math
import re
import statistics
from pathlib import Path
from typing import Optional

from ..taxonomy import ALL_METRICS, map_label
from .extract import _to_number
from .models import ExtractedMetric, parse_period

_YEAR_RE = re.compile(r"^(19|20)\d{2}$")
_MONTH_Q = {  # month a period ENDS in -> the quarter that ends there
    "january": 1, "february": 1, "march": 1,
    "april": 2, "may": 2, "june": 2,
    "july": 3, "august": 3, "september": 3,
    "october": 4, "november": 4, "december": 4,
}


def _xc(t) -> float:
    """x-center of a token."""
    return t.x + t.width / 2.0


def _has_alpha(s: str) -> bool:
    return any(c.isalpha() for c in s)


def _estimate_skew_deg(items, max_deg: float = 5.0, step: float = 0.25) -> float:
    """Estimate page skew from token baselines (projection-profile over token centroids).

    A crooked scan tilts every row: on a page rotated by θ, tokens that belong to one logical
    row no longer share a y. We pick the θ in [-max,max] that, after de-rotating y by
    `y - (x-cx)*tan θ`, packs tokens into the FEWEST, TIGHTEST horizontal bands (max sum of
    squared bin counts). Deterministic, cheap (tens of tokens), and it never guesses which
    label owns which value — it only corrects the row geometry.
    """
    if len(items) < 4:
        return 0.0
    xs = [_xc(t) for t in items]
    cx = sum(xs) / len(xs)
    bh = (statistics.median([t.height for t in items]) or 1.0) * 0.8
    best_deg, best_score = 0.0, -1.0
    deg = -max_deg
    while deg <= max_deg + 1e-9:
        t = math.tan(math.radians(deg))
        bins: dict[int, int] = {}
        for it in items:
            yb = round((it.y - (_xc(it) - cx) * t) / bh)
            bins[yb] = bins.get(yb, 0) + 1
        score = sum(c * c for c in bins.values())   # higher = tokens concentrated in fewer rows
        if score > best_score:
            best_deg, best_score = deg, score
        deg += step
    return best_deg


def cluster_rows(items, y_tol_factor: float = 0.6) -> list[tuple[float, list]]:
    """Group tokens into visual rows by (deskewed) y. Returns [(row_y, [tokens sorted by x]), ...].

    Corrects scan skew first so a tilted row's label and values cluster together; the returned
    tokens are the originals (only the grouping key is de-rotated, x is untouched for columns).
    """
    if not items:
        return []
    tol = statistics.median([t.height for t in items]) * y_tol_factor
    deg = _estimate_skew_deg(items)
    tan = math.tan(math.radians(deg))
    cx = sum(_xc(t) for t in items) / len(items)
    ykey = lambda t: t.y - (_xc(t) - cx) * tan      # deskewed row position
    rows: list[list] = []
    keys: list[float] = []
    for t in sorted(items, key=lambda i: (ykey(i), i.x)):
        k = ykey(t)
        if rows and abs(k - keys[-1]) <= tol:
            rows[-1].append(t)
            keys[-1] = (keys[-1] + k) / 2.0
        else:
            rows.append([t])
            keys.append(k)
    return [(k, sorted(r, key=lambda i: i.x)) for k, r in zip(keys, rows)]


def _find_anchor_row(rows) -> Optional[int]:
    """Index of the column-header row: >=2 tokens that are years or 'Qn YYYY'."""
    for idx, (_, toks) in enumerate(rows):
        markers = [t for t in toks if _YEAR_RE.match(t.text.strip()) or parse_period(t.text)]
        if len(markers) >= 2:
            return idx
    return None


def _period_for_column(rows, anchor_idx: int, x_center: float, anchor_tok) -> Optional[str]:
    """Infer a canonical period for one column from the stacked header above the anchor row."""
    # direct hit: the anchor token is already 'Qn YYYY'
    direct = parse_period(anchor_tok.text)
    if direct:
        return direct

    year = anchor_tok.text.strip() if _YEAR_RE.match(anchor_tok.text.strip()) else None

    # gather header context: in each header row above, take the nearest token AT OR LEFT of
    # this column. Group headers ('Three Months Ended') sit at the left of their sub-columns,
    # so nearest-left correctly broadcasts them across every sub-column they govern (a pure
    # span-overlap test under-reaches: OCR width often covers only the first sub-column).
    ctx: list[str] = []
    for i in range(anchor_idx):
        left = [t for t in rows[i][1] if t.x <= x_center + 2]
        if left:
            ctx.append(max(left, key=lambda t: t.x).text.strip())
    blob = " ".join(ctx).lower()

    if not year:  # try to find a year anywhere in the column's header context
        ym = re.search(r"(19|20)\d{2}", blob)
        year = ym.group(0) if ym else None
    if not year:
        return None

    # explicit quarter in the header wins
    qm = re.search(r"q\s*([1-4])", blob)
    if qm:
        return f"Q{qm.group(1)} {year}"
    # "Three/Six/Nine/Twelve Months Ended <month>" -> quarter or YTD label
    period_words = re.search(r"(three|six|nine|twelve)\s+months", blob)
    month = next((m for m in _MONTH_Q if m in blob), None)
    if period_words:
        span = period_words.group(1)
        if span == "three" and month:
            return f"Q{_MONTH_Q[month]} {year}"   # single quarter
        if span == "six":
            return f"6M {year}"
        if span == "nine":
            return f"9M {year}"
        if span == "twelve":
            return f"FY {year}"
    if month:  # a quarter-end month with no span context -> treat as that quarter
        return f"Q{_MONTH_Q[month]} {year}"
    return f"FY {year}"   # bare year column


def reconstruct_metrics_from_tokens(items, *, source_file: str, page: int) -> list[ExtractedMetric]:
    """Token list (one page) -> ExtractedMetric rows. Mirrors extract_from_excel's contract."""
    rows = cluster_rows(items)
    anchor_idx = _find_anchor_row(rows)
    if anchor_idx is None:
        return []

    anchor_toks = [
        t for t in rows[anchor_idx][1]
        if _YEAR_RE.match(t.text.strip()) or parse_period(t.text)
    ]
    columns: list[tuple[float, str]] = []   # (x_center, period)
    for t in anchor_toks:
        period = _period_for_column(rows, anchor_idx, _xc(t), t)
        if period:
            columns.append((_xc(t), period))
    if not columns:
        return []
    columns.sort()
    col_xs = [c[0] for c in columns]
    first_col_x = col_xs[0]
    # snap tolerance = ~half the min column spacing (fallback to a generous default)
    spacings = [b - a for a, b in zip(col_xs, col_xs[1:])]
    snap_tol = (min(spacings) / 2.0) if spacings else 40.0
    label_cutoff = first_col_x - snap_tol

    out: list[ExtractedMetric] = []
    for ridx in range(anchor_idx + 1, len(rows)):
        _, toks = rows[ridx]
        label_parts = [t.text.strip() for t in toks if _xc(t) < label_cutoff and _has_alpha(t.text)]
        label = " ".join(label_parts).strip()
        if not label:
            continue
        metric_type = map_label(label)
        unit = ALL_METRICS[metric_type].unit.value if metric_type else None
        for t in toks:
            if _xc(t) < label_cutoff:
                continue
            val = _to_number(t.text)
            if val is None:
                continue
            # snap to nearest column anchor
            ci = min(range(len(col_xs)), key=lambda i: abs(col_xs[i] - _xc(t)))
            if abs(col_xs[ci] - _xc(t)) > snap_tol:
                continue
            period = columns[ci][1]
            out.append(ExtractedMetric(
                raw_label=label,
                metric_type=metric_type,
                period=period,
                value=val,
                unit=unit,
                source_file=source_file,
                tab=f"page {page}",
                cell_ref=f"p{page}@{round(t.x)},{round(t.y)}",
                confidence=round(float(getattr(t, "confidence", 0.0) or 0.0), 3),
            ))
    return out


def parse_image_pdf(path: str | Path, **liteparse_kwargs) -> tuple[list[ExtractedMetric], list[tuple[int, str]]]:
    """Single LiteParse pass over an image PDF -> (metrics, [(page_no, ocr_text), ...]).

    One OCR pass feeds BOTH pipelines: positioned tokens -> reconstructed metrics (Pipeline A)
    and the raw page text -> narrative chunks (Pipeline B). Board packs carry both numbers and
    commentary on the same pages, so ingest routes an image PDF through both off this one pass.
    """
    from liteparse import LiteParse

    path = Path(path)
    parser = LiteParse(quiet=True, **liteparse_kwargs)
    result = parser.parse(path)
    metrics: list[ExtractedMetric] = []
    pages_text: list[tuple[int, str]] = []
    for pno, page in enumerate(result.pages, start=1):
        metrics.extend(reconstruct_metrics_from_tokens(
            page.text_items, source_file=path.name, page=pno))
        pages_text.append((pno, page.text or ""))
    return metrics, pages_text


def extract_from_image_pdf(path: str | Path, **liteparse_kwargs) -> list[ExtractedMetric]:
    """Image-only PDF -> ExtractedMetric rows via LiteParse OCR + geometric reconstruction.

    Drop-in sibling of `extract_from_excel`: same return type, same downstream (validate,
    variance, one-pager). `liteparse_kwargs` pass through to `LiteParse(...)`.
    """
    metrics, _ = parse_image_pdf(path, **liteparse_kwargs)
    return metrics
