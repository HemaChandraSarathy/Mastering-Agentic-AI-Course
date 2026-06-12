"""Golden set for Pipeline A extraction accuracy — '(document) -> expected (metric, period, value)'.

This is the numbers-side counterpart to `questions.py` (the narrative-RAG golden). It pins
hand-authored expected metric rows for each extraction engine so we can score exact-match
accuracy, recall, precision, and provenance coverage — and catch OCR / table-parse / mapping
regressions automatically.

Truth provenance (deliberately independent of the extractor, to avoid a circular benchmark):
  - Excel (Meridian)  : the values authored in `scripts/make_sample_data.py` (our own generator).
  - Text PDF (Atlas)  : the literals authored in `make_extraction_fixtures.py`.
  - Image PDF (10-Q)  : the published ConocoPhillips Q3'25 10-Q income-statement figures
                        (public filing; labeled placeholder), cross-checked by the reconciliation
                        identities (net = pretax - tax; pretax = revenues - costs).

`complete=True` means the golden lists EVERY mapped metric the engine should produce on that
fixture, so unexpected extras are scored as false positives (precision). `complete=False`
scores recall only (extras tolerated).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoldenRow:
    metric_type: str
    period: str
    value: float


@dataclass
class GoldenDoc:
    name: str
    fixture: str           # path relative to repo root
    engine: str            # 'excel' | 'text_pdf' | 'image_pdf'
    truth_source: str
    complete: bool
    rows: list = field(default_factory=list)
    value_tol: float = 0.5


def _expand(periods: list[str], pairs: list[tuple[str, list[float]]]) -> list[GoldenRow]:
    """pairs: [(metric_type, [v aligned to `periods`]), ...] -> flat GoldenRow list."""
    out: list[GoldenRow] = []
    for mt, vals in pairs:
        for per, v in zip(periods, vals):
            out.append(GoldenRow(mt, per, float(v)))
    return out


# --- Excel: Meridian (authored in scripts/make_sample_data.py) ----------------
_MERIDIAN_PERIODS = ["Q3 2024", "Q1 2025", "Q2 2025", "Q3 2025"]
_MERIDIAN = _expand(_MERIDIAN_PERIODS, [
    ("revenue",                    [98.0, 102.0, 105.0, 110.0]),
    ("total_costs_and_expenses",   [84.0, 87.0, 89.0, 92.0]),
    ("income_before_income_taxes", [14.0, 15.0, 16.0, 18.0]),
    ("income_tax_expense",         [3.5, 3.8, 4.0, 4.5]),
    ("net_income",                 [10.5, 11.2, 12.0, 13.5]),
    ("ebitda",                     [18.0, 19.0, 19.8, 20.5]),
    ("gross_margin",               [34.0, 34.5, 34.2, 35.0]),
    ("working_capital",            [45.0, 47.0, 48.0, 50.0]),
    ("headcount",                  [1180, 1190, 1205, 1220]),
    ("dso",                        [52, 51, 50, 49]),
    ("net_debt",                   [210.0, 205.0, 200.0, 195.0]),
    ("cash",                       [25.0, 28.0, 30.0, 32.0]),
    ("leverage_ratio",             [2.8, 2.7, 2.6, 2.5]),
])

# --- Text PDF: Atlas (authored in make_extraction_fixtures.py) ----------------
_ATLAS_PERIODS = ["Q1 2025", "Q2 2025", "Q3 2025"]
_ATLAS = _expand(_ATLAS_PERIODS, [
    ("revenue",      [120.0, 135.0, 150.0]),
    ("ebitda",       [30.0, 33.0, 31.0]),
    ("gross_margin", [62.0, 61.0, 58.0]),
    ("headcount",    [410.0, 430.0, 455.0]),
    ("net_debt",     [200.0, 195.0, 188.0]),
])

# --- Image PDF: ConocoPhillips Q3'25 10-Q income statement (real, reconciled) --
# Column order: Three-months Q3'25, Three-months Q3'24, Nine-months '25, Nine-months '24.
_COP_PERIODS = ["Q3 2025", "Q3 2024", "9M 2025", "9M 2024"]
_COP = _expand(_COP_PERIODS, [
    ("revenue",                    [15031, 13041, 45552, 40509]),
    ("total_revenues",             [15522, 13604, 47363, 42216]),
    ("total_costs_and_expenses",   [12594, 10369, 36952, 31514]),
    ("income_before_income_taxes", [2928, 3235, 10411, 10702]),
    ("income_tax_expense",         [1202, 1176, 3865, 3763]),
    ("net_income",                 [1726, 2059, 6546, 6939]),
])


# --- Image PDF: deliberately MESSY board pack (two tables, merged header, 1.5° skew) ---
_VESPER_PERIODS = ["Q2 2025", "Q3 2025"]
_VESPER = _expand(_VESPER_PERIODS, [
    ("revenue",    [135.0, 150.0]),
    ("ebitda",     [33.0, 31.0]),
    ("net_income", [12.0, 13.5]),
    ("net_debt",   [195.0, 188.0]),
    ("cash",       [30.0, 32.0]),
])


GOLDEN: list[GoldenDoc] = [
    GoldenDoc(
        name="Meridian financials (Excel)",
        fixture="corpus/sample/meridian/meridian_SAMPLE_financials.xlsx",
        engine="excel",
        truth_source="authored in scripts/make_sample_data.py (3 tabs, 13 line items x 4 periods)",
        complete=True,
        rows=_MERIDIAN,
    ),
    GoldenDoc(
        name="Atlas summary (text-layer PDF)",
        fixture="eval/fixtures/text_financials.pdf",
        engine="text_pdf",
        truth_source="authored table in make_extraction_fixtures.py (pdfplumber table path)",
        complete=True,
        rows=_ATLAS,
    ),
    GoldenDoc(
        name="ConocoPhillips Q3'25 10-Q (image-only PDF)",
        fixture="eval/fixtures/image_boardpack.pdf",
        engine="image_pdf",
        truth_source="published COP Q3'25 10-Q income statement; verified by reconciliation",
        complete=True,
        rows=_COP,
        value_tol=0.5,
    ),
    GoldenDoc(
        name="Vesper board pack (MESSY image: 2 tables, merged header, 1.5° skew)",
        fixture="eval/fixtures/messy_boardpack.pdf",
        engine="image_pdf",
        truth_source="authored in make_extraction_fixtures.py; stress-tests deskew + multi-table",
        complete=True,
        rows=_VESPER,
        value_tol=0.5,
    ),
]
