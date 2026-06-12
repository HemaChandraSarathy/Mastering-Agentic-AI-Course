"""Regenerate the durable Pipeline A extraction fixtures into eval/fixtures/.

Three fixtures, one per extraction engine the golden set scores:
  - text_financials.pdf  — a TEXT-layer PDF with a financial table (pdfplumber path)
  - image_boardpack.pdf  — an IMAGE-only PDF of a real income statement (LiteParse OCR path)
  - (Excel)              — referenced in place at corpus/sample/meridian/meridian_SAMPLE_financials.xlsx

The text PDF's numbers are authored here (so the golden's expected values are independent of
the extractor). The image PDF is rendered from a real ConocoPhillips Q3'25 10-Q page image
(public filing; labeled placeholder, not customer data); its golden values are the published
filing figures, cross-checked by income-statement reconciliation.

Run:  .venv/Scripts/python.exe eval/make_extraction_fixtures.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "eval" / "fixtures"
PNG_SOURCE = ROOT / "_scratch" / "Q3 2025 Quarterly Report_p1.png"  # real 10-Q page image

# Authored content for the text-PDF table — these literals ARE the golden truth for it.
TEXT_PDF_TABLE = [
    ["Metric", "Q1 2025", "Q2 2025", "Q3 2025"],
    ["Revenue", "120", "135", "150"],
    ["EBITDA", "30", "33", "31"],
    ["Gross margin", "62", "61", "58"],
    ["Headcount", "410", "430", "455"],
    ["Net debt", "200", "195", "188"],
]


def make_text_pdf() -> Path:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    out = FIX / "text_financials.pdf"
    doc = SimpleDocTemplate(str(out), pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Project Atlas — Quarterly Financial Summary (text-layer PDF)", styles["Title"]),
        Paragraph("Management commentary: revenue grew on new-logo wins while gross margin "
                  "compressed on cloud costs. This prose flows to Pipeline B (narrative); the "
                  "table below flows to Pipeline A (deterministic numbers).", styles["Normal"]),
        Spacer(1, 12),
    ]
    t = Table(TEXT_PDF_TABLE)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
    ]))
    story.append(t)
    doc.build(story)
    return out


# Authored content for the MESSY fixture — these literals ARE its golden truth.
# Deliberately hard: two tables on one page, a merged group header, a 1.5° scan skew, and a
# label/value layout that desynchronizes under skew. Exercises deskew + robustness.
MESSY_T1 = [("Revenue", "135", "150"), ("EBITDA", "33", "31"), ("Net income", "12.0", "13.5")]
MESSY_T2 = [("Net debt", "195", "188"), ("Cash and cash equivalents", "30", "32")]


def make_messy_image_pdf() -> Path:
    from PIL import Image, ImageDraw, ImageFont
    f = lambda s, b=False: ImageFont.truetype("arialbd.ttf" if b else "arial.ttf", s)
    img = Image.new("RGB", (1240, 1600), "white")
    d = ImageDraw.Draw(img)
    d.text((60, 40), "Project Vesper — Board Pack (messy scan)", font=f(30, True), fill="black")
    # table 1: P&L with a MERGED 'Three Months Ended' header spanning the two period columns
    d.text((60, 120), "Quarterly P&L ($ in millions)", font=f(22, True), fill="black")
    d.text((520, 160), "Three Months Ended", font=f(18, True), fill="black")
    d.text((545, 188), "Q2 2025", font=f(18, True), fill="black")
    d.text((690, 188), "Q3 2025", font=f(18, True), fill="black")
    y = 224
    for lab, a, b in MESSY_T1:
        d.text((60, y), lab, font=f(18), fill="black")
        d.text((560, y), a, font=f(18), fill="black")
        d.text((705, y), b, font=f(18), fill="black")
        y += 34
    # table 2: a SEPARATE liquidity table lower on the same page, with its own header
    d.text((60, 420), "Liquidity ($M)", font=f(22, True), fill="black")
    d.text((545, 452), "Q2 2025", font=f(18, True), fill="black")
    d.text((690, 452), "Q3 2025", font=f(18, True), fill="black")
    y = 488
    for lab, a, b in MESSY_T2:
        d.text((60, y), lab, font=f(18), fill="black")
        d.text((560, y), a, font=f(18), fill="black")
        d.text((705, y), b, font=f(18), fill="black")
        y += 34
    img = img.rotate(1.5, expand=True, fillcolor="white")     # crooked scan
    out = FIX / "messy_boardpack.pdf"
    img.convert("RGB").save(out, "PDF", resolution=150.0)
    return out


def make_image_pdf() -> Path | None:
    if not PNG_SOURCE.exists():
        print(f"  ! source image missing: {PNG_SOURCE.name} — skipping image fixture")
        return None
    from PIL import Image
    # keep a copy of the source image in fixtures for full reproducibility
    shutil.copyfile(PNG_SOURCE, FIX / "boardpack_source.png")
    out = FIX / "image_boardpack.pdf"
    Image.open(PNG_SOURCE).convert("RGB").save(out, "PDF", resolution=150.0)
    return out


def main() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    tp = make_text_pdf()
    print(f"  wrote {tp.relative_to(ROOT)}")
    ip = make_image_pdf()
    if ip:
        print(f"  wrote {ip.relative_to(ROOT)}")
    mp = make_messy_image_pdf()
    print(f"  wrote {mp.relative_to(ROOT)}")
    print("fixtures ready in eval/fixtures/")


if __name__ == "__main__":
    main()
