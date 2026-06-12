"""Score Pipeline A extraction against the golden set -> eval/runs/extraction_report.md.

Runs the right extractor per fixture (Excel / text-PDF tables / image-PDF OCR), compares the
mapped output to the hand-authored golden, and reports per-engine and overall:
  - Recall          = matched / expected            (did we get every known value?)
  - Precision       = matched / (matched + value-errors + unexpected)   (no wrong/spurious values)
  - Exact-match     = matched / expected            (value within tolerance AND right metric+period)
  - Provenance cov. = % of extracted metrics carrying a cell_ref / bbox

No network, no LLM — pure deterministic check. Run:
  .venv/Scripts/python.exe eval/run_extraction_eval.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.golden_extraction import GOLDEN, GoldenDoc                      # noqa: E402
from src.portcoiq_rag.pipeline_a.extract import (                        # noqa: E402
    extract_from_excel, extract_from_text_pdf)
from src.portcoiq_rag.pipeline_a.reconstruct import extract_from_image_pdf  # noqa: E402

_EXTRACTORS = {
    "excel": extract_from_excel,
    "text_pdf": extract_from_text_pdf,
    "image_pdf": extract_from_image_pdf,
}


def _score(doc: GoldenDoc) -> dict:
    metrics = _EXTRACTORS[doc.engine](ROOT / doc.fixture)
    mapped = [m for m in metrics if m.metric_type]
    # first value wins per (metric_type, period) — mirrors downstream dedup
    got: dict[tuple, float] = {}
    got_ref: dict[tuple, bool] = {}
    for m in mapped:
        key = (m.metric_type, m.period)
        if key not in got:
            got[key] = m.value
            got_ref[key] = bool(m.cell_ref)

    expected_keys = {(r.metric_type, r.period) for r in doc.rows}
    matched, value_errors, missing = [], [], []
    for r in doc.rows:
        key = (r.metric_type, r.period)
        if key not in got:
            missing.append(r)
        elif abs(got[key] - r.value) <= doc.value_tol:
            matched.append(r)
        else:
            value_errors.append((r, got[key]))
    unexpected = [k for k in got if k not in expected_keys] if doc.complete else []

    n_exp = len(doc.rows)
    recall = len(matched) / n_exp if n_exp else 0.0
    denom = len(matched) + len(value_errors) + len(unexpected)
    precision = len(matched) / denom if denom else 1.0
    prov = (sum(1 for v in got_ref.values() if v) / len(got_ref)) if got_ref else 0.0
    return {
        "doc": doc, "n_expected": n_exp, "n_got": len(got),
        "matched": matched, "value_errors": value_errors, "missing": missing,
        "unexpected": unexpected, "recall": recall, "precision": precision, "prov": prov,
    }


def main() -> None:
    results = [_score(d) for d in GOLDEN]

    tot_exp = sum(r["n_expected"] for r in results)
    tot_match = sum(len(r["matched"]) for r in results)
    tot_verr = sum(len(r["value_errors"]) for r in results)
    tot_miss = sum(len(r["missing"]) for r in results)
    tot_unexp = sum(len(r["unexpected"]) for r in results)
    overall_recall = tot_match / tot_exp if tot_exp else 0.0
    overall_prec = tot_match / (tot_match + tot_verr + tot_unexp) if (tot_match + tot_verr + tot_unexp) else 1.0

    print("=" * 72)
    print("PIPELINE A — EXTRACTION GOLDEN EVAL")
    print("=" * 72)
    for r in results:
        d = r["doc"]
        print(f"\n{d.name}  [{d.engine}]")
        print(f"  expected {r['n_expected']} | matched {len(r['matched'])} | "
              f"value-err {len(r['value_errors'])} | missing {len(r['missing'])} | "
              f"unexpected {len(r['unexpected'])}")
        print(f"  recall {r['recall']:.2f} | precision {r['precision']:.2f} | provenance {r['prov']*100:.0f}%")
        for row, gotv in r["value_errors"]:
            print(f"    VALUE-ERR {row.metric_type} {row.period}: golden {row.value:g} != got {gotv:g}")
        for row in r["missing"]:
            print(f"    MISSING   {row.metric_type} {row.period} (= {row.value:g})")
        for key in r["unexpected"]:
            print(f"    UNEXPECTED {key[0]} {key[1]}")
    print(f"\nOVERALL  recall {overall_recall:.3f} | precision {overall_prec:.3f} | "
          f"{tot_match}/{tot_exp} exact across {len(results)} fixtures")

    # --- markdown report ---
    lines = [
        "# Pipeline A — extraction golden eval",
        "",
        "_Deterministic numbers benchmark: each fixture's extractor output vs hand-authored truth._",
        "_Truth is independent of the extractor (authored generators / published filing) to avoid a circular benchmark._",
        "",
        "| Fixture | Engine | Expected | Matched | Value-err | Missing | Unexpected | Recall | Precision | Provenance |",
        "|---|---|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for r in results:
        d = r["doc"]
        lines.append(
            f"| {d.name} | `{d.engine}` | {r['n_expected']} | {len(r['matched'])} | "
            f"{len(r['value_errors'])} | {len(r['missing'])} | {len(r['unexpected'])} | "
            f"{r['recall']:.2f} | {r['precision']:.2f} | {r['prov']*100:.0f}% |")
    lines += [
        f"| **Overall** | — | **{tot_exp}** | **{tot_match}** | {tot_verr} | {tot_miss} | {tot_unexp} | "
        f"**{overall_recall:.3f}** | **{overall_prec:.3f}** | — |",
        "",
        "## Definitions",
        "- **Recall** = matched / expected — did we extract every known value?",
        "- **Precision** = matched / (matched + value-errors + unexpected) — no wrong or spurious values "
        "(`complete=True` fixtures score spurious extras as false positives).",
        "- **Provenance** = % of extracted metrics carrying a `cell_ref` / bbox (the transparency triad's source).",
        "- A match requires the right **metric_type + period** AND a value within the fixture's tolerance.",
        "",
        "## Per-fixture truth source",
    ]
    for r in results:
        d = r["doc"]
        lines.append(f"- **{d.name}** (`{d.fixture}`) — {d.truth_source}")

    # surface any defects so the report never silently hides a miss
    defects = [(r["doc"].name, r["value_errors"], r["missing"], r["unexpected"])
               for r in results if r["value_errors"] or r["missing"] or r["unexpected"]]
    lines += ["", "## Defects"]
    if not defects:
        lines.append("None — every golden value matched exactly, no spurious or missing metrics.")
    else:
        for name, verr, miss, unexp in defects:
            for row, gotv in verr:
                lines.append(f"- {name}: VALUE-ERR {row.metric_type} {row.period} golden {row.value:g} != got {gotv:g}")
            for row in miss:
                lines.append(f"- {name}: MISSING {row.metric_type} {row.period} (= {row.value:g})")
            for key in unexp:
                lines.append(f"- {name}: UNEXPECTED {key[0]} {key[1]}")

    out = ROOT / "eval" / "runs" / "extraction_report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
