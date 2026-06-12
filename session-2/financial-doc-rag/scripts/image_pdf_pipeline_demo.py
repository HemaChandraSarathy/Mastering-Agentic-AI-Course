"""End-to-end: image-only PDF -> metrics -> validate -> variance, the full Pipeline A.

Proves an image PDF (no text layer) now flows through the SAME deterministic downstream as
a messy Excel: LiteParse OCR -> geometric row/column reconstruction -> taxonomy map ->
reconciliation checks -> period variance. Contrast with the current pdfplumber path, which
returns nothing on an image-only page.

Run:  .venv/Scripts/python.exe scripts/image_pdf_pipeline_demo.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.portcoiq_rag.pipeline_a.reconstruct import extract_from_image_pdf  # noqa: E402
from src.portcoiq_rag.pipeline_a.validate import validate                    # noqa: E402
from src.portcoiq_rag.pipeline_a.variance import compute_variance            # noqa: E402

FIXTURE = ROOT / "_scratch" / "trial_boardpack.pdf"
_QUARTER = re.compile(r"^Q[1-4]\s+\d{4}$")


def run_pdfplumber_baseline() -> int:
    """Current path: pdfplumber over the image PDF. Pipeline A is Excel-only, so this is 0."""
    import pdfplumber
    with pdfplumber.open(FIXTURE) as pdf:
        txt = pdf.pages[0].extract_text() or ""
    return len(txt)


def main() -> None:
    print("=" * 72)
    print("IMAGE-ONLY PDF -> FULL PIPELINE A (extract -> validate -> variance)")
    print("=" * 72)

    base_chars = run_pdfplumber_baseline()
    print(f"\n[BEFORE] pdfplumber on the image PDF: {base_chars} chars -> "
          f"0 metrics (no text layer; Pipeline A had no PDF path).")

    # AFTER: LiteParse OCR -> reconstruct -> the existing downstream, unchanged
    metrics = extract_from_image_pdf(FIXTURE)
    mapped = [m for m in metrics if m.metric_type]
    quarters = sorted({m.period for m in mapped if _QUARTER.match(m.period)})
    ytd = sorted({m.period for m in mapped if not _QUARTER.match(m.period)})

    print(f"\n[AFTER]  LiteParse OCR -> reconstruct: {len(metrics)} values "
          f"({len(mapped)} mapped to taxonomy, {len(metrics) - len(mapped)} unmapped & surfaced).")
    print(f"         Quarter columns: {quarters}   YTD columns (excluded from QoQ): {ytd}")

    # 1) validation — reconciliation identities on the OCR'd numbers
    flags = validate(mapped)
    errs = [f for f in flags if f.severity == "error"]
    print(f"\n--- VALIDATION ({len(flags)} flag(s), {len(errs)} error) ---")
    if not flags:
        print("  All range/comparison/formula checks PASS — incl. reconciliation:")
        print("    income_before_taxes == total_revenues - total_costs")
        print("    net_income          == income_before_taxes - income_tax")
        print("  => OCR'd figures are internally consistent (high-trust extraction).")
    for f in flags:
        print(f"  [{f.severity}] {f.period} {f.rule}: {f.message}")

    # 2) variance — QoQ machinery over the quarter columns only (here Q3'24 -> Q3'25 = YoY pair)
    q_metrics = [m for m in mapped if _QUARTER.match(m.period)]
    var = compute_variance(q_metrics)
    print(f"\n--- VARIANCE (quarter columns; this 10-Q page yields a Q3'24->Q3'25 YoY pair) ---")
    print(f"    {'metric':28} {'period':9} {'value':>10} {'prior':>10} {'chg':>9}  flag")
    for v in sorted(var, key=lambda r: (r.metric_type, r.period)):
        if v.prior_value is None:
            continue
        pct = f"{v.qoq_pct * 100:+.1f}%" if v.qoq_pct is not None else "—"
        flag = "  <-- >=10%" if v.flagged else ""
        print(f"    {v.metric_type:28} {v.period:9} {v.value:>10,.0f} "
              f"{v.prior_value:>10,.0f} {pct:>9}{flag}")

    print(f"\nProvenance sample (bbox + OCR confidence carried end-to-end):")
    for m in mapped[:3]:
        print(f"    {m.metric_type} {m.period} = {m.value:,.0f}  @ {m.cell_ref}  conf={m.confidence}")

    print("\nSame validate/variance/one-pager code as the Excel path — only the extractor changed.")


if __name__ == "__main__":
    main()
