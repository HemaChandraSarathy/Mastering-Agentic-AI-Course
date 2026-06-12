# Pipeline A — extraction golden eval

_Deterministic numbers benchmark: each fixture's extractor output vs hand-authored truth._
_Truth is independent of the extractor (authored generators / published filing) to avoid a circular benchmark._

| Fixture | Engine | Expected | Matched | Value-err | Missing | Unexpected | Recall | Precision | Provenance |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Meridian financials (Excel) | `excel` | 52 | 52 | 0 | 0 | 0 | 1.00 | 1.00 | 100% |
| Atlas summary (text-layer PDF) | `text_pdf` | 15 | 15 | 0 | 0 | 0 | 1.00 | 1.00 | 100% |
| ConocoPhillips Q3'25 10-Q (image-only PDF) | `image_pdf` | 24 | 24 | 0 | 0 | 0 | 1.00 | 1.00 | 100% |
| Vesper board pack (MESSY image: 2 tables, merged header, 1.5° skew) | `image_pdf` | 10 | 8 | 0 | 2 | 0 | 0.80 | 1.00 | 100% |
| **Overall** | — | **101** | **99** | 0 | 2 | 0 | **0.980** | **1.000** | — |

## Definitions
- **Recall** = matched / expected — did we extract every known value?
- **Precision** = matched / (matched + value-errors + unexpected) — no wrong or spurious values (`complete=True` fixtures score spurious extras as false positives).
- **Provenance** = % of extracted metrics carrying a `cell_ref` / bbox (the transparency triad's source).
- A match requires the right **metric_type + period** AND a value within the fixture's tolerance.

## Per-fixture truth source
- **Meridian financials (Excel)** (`corpus/sample/meridian/meridian_SAMPLE_financials.xlsx`) — authored in scripts/make_sample_data.py (3 tabs, 13 line items x 4 periods)
- **Atlas summary (text-layer PDF)** (`eval/fixtures/text_financials.pdf`) — authored table in make_extraction_fixtures.py (pdfplumber table path)
- **ConocoPhillips Q3'25 10-Q (image-only PDF)** (`eval/fixtures/image_boardpack.pdf`) — published COP Q3'25 10-Q income statement; verified by reconciliation
- **Vesper board pack (MESSY image: 2 tables, merged header, 1.5° skew)** (`eval/fixtures/messy_boardpack.pdf`) — authored in make_extraction_fixtures.py; stress-tests deskew + multi-table

## Defects
- Vesper board pack (MESSY image: 2 tables, merged header, 1.5° skew): MISSING cash Q2 2025 (= 30)
- Vesper board pack (MESSY image: 2 tables, merged header, 1.5° skew): MISSING cash Q3 2025 (= 32)
