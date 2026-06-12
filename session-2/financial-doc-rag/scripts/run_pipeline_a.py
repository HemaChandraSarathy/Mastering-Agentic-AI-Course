"""Run Pipeline A end-to-end on a file and print extraction → validation → variance.

Usage: python scripts/run_pipeline_a.py [path-to-xlsx]
Defaults to the synthetic Conoco workbook.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from portcoiq_rag.pipeline_a.extract import extract_from_excel
from portcoiq_rag.pipeline_a.validate import validate
from portcoiq_rag.pipeline_a.variance import compute_variance

REPO = Path(__file__).resolve().parents[1]
default = REPO / "corpus" / "ConocoPhillips_SYNTHETIC_financials.xlsx"
path = Path(sys.argv[1]) if len(sys.argv) > 1 else default

sys.stdout.reconfigure(encoding="utf-8")  # Windows console defaults to cp1252

metrics = extract_from_excel(path)
mapped = [m for m in metrics if m.mapped]
unmapped = sorted({m.raw_label for m in metrics if not m.mapped})

print(f"\n=== EXTRACTION — {path.name} ===")
print(f"{len(metrics)} values extracted · {len(mapped)} mapped · {len(metrics) - len(mapped)} unmapped\n")
print(f"{'metric_type':<28}{'period':<10}{'value':>12}   source")
for m in sorted(mapped, key=lambda x: (x.metric_type, x.period)):
    print(f"{m.metric_type:<28}{m.period:<10}{m.value:>12,.2f}   {m.tab}!{m.cell_ref}")

print(f"\n  unmapped labels (surfaced to analyst, not dropped): {unmapped}")

print(f"\n=== VALIDATION ===")
flags = validate(metrics)
if not flags:
    print("  no violations — all reconciliation identities hold.")
for f in flags:
    print(f"  [{f.severity.upper():7}] {f.period}  {f.message}")

print(f"\n=== VARIANCE (period-over-period) ===")
rows = compute_variance(metrics)
print(f"{'metric_type':<28}{'period':<10}{'value':>12}{'QoQ %':>10}  flag")
for r in sorted(rows, key=lambda x: (x.metric_type, x.period)):
    qoq = f"{r.qoq_pct*100:+.1f}%" if r.qoq_pct is not None else "   —"
    flag = "⚠" if r.flagged else ""
    print(f"{r.metric_type:<28}{r.period:<10}{r.value:>12,.2f}{qoq:>10}  {flag}")
print()
