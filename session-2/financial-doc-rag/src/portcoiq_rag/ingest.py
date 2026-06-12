"""Unified, incremental, company-scoped ingest → Supabase.

Routing by file type / content:
  - .xlsx/.xls       → Pipeline A (extract → validate → variance)        → rag_metrics
  - .pdf (text layer)→ BOTH: pdfplumber tables → Pipeline A numbers      → rag_metrics
                             page text → Pipeline B narrative chunks     → rag_chunks
  - .pdf (image-only)→ LiteParse OCR, ONE pass → BOTH:
                         tokens → reconstruct → Pipeline A numbers       → rag_metrics
                         page text → Pipeline B narrative chunks         → rag_chunks
  - .txt / .md       → Pipeline B (chunk → embed)                        → rag_chunks

Numbers ALWAYS come from a deterministic path (Excel cells, pdfplumber table cells, or OCR
token reconstruction) — never from narrative RAG. A text PDF's tables go to Pipeline A even
though its prose goes to Pipeline B.
Every row is tagged with company_id (slug) + firm_id so the data is multi-tenant-shaped.

Image-only PDFs (board packs) used to be skipped entirely (no text layer). They now flow
through both pipelines off a single OCR pass. Validation + variance run ONCE over the
combined Excel + image-PDF metric set so periods reconcile across sources.
"""
from __future__ import annotations

import re
from pathlib import Path

from .pipeline_a.extract import extract_from_excel, extract_from_text_pdf
from .pipeline_a.models import ExtractedMetric
from .pipeline_a.reconstruct import parse_image_pdf
from .pipeline_a.validate import validate
from .pipeline_a.variance import compute_variance
from .pipeline_b import store
from .pipeline_b.chunkers import structural_chunks
from .pipeline_b.embed import embed_chunks
from .pipeline_b.loaders import load_pdf, load_text, ocr_doc_from_pages

DEFAULT_FIRM = "demo-firm"
_CONF = {"ok": 1.0, "warning": 0.6, "error": 0.3}  # extraction confidence by validation status
_QUARTER = re.compile(r"^Q[1-4]\s+\d{4}$")          # only true quarters take part in QoQ variance


def company_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "company").lower()).strip("-") or "company"


def _build_metric_rows(metrics: list[ExtractedMetric], company: str, company_id: str,
                       firm_id: str) -> list[dict]:
    """Validate + variance over all Pipeline A metrics, emit rag_metrics rows.

    Variance is computed over quarter-form periods only; YTD columns (e.g. '9M 2025') are
    stored but carry no QoQ (you don't compare a quarter to a year-to-date figure)."""
    flags = validate(metrics)
    var = compute_variance([m for m in metrics if _QUARTER.match(m.period)])
    sev = {(f.metric_type, f.period): f.severity for f in flags if f.metric_type and f.period}
    vpct = {(v.metric_type, v.period): v.qoq_pct for v in var}
    rows = []
    for m in metrics:
        if not m.metric_type:
            continue
        status = sev.get((m.metric_type, m.period), "ok")
        rows.append({
            "company": company, "company_id": company_id, "firm_id": firm_id,
            "metric_type": m.metric_type, "raw_label": m.raw_label, "period": m.period,
            "value": m.value, "unit": m.unit, "source_file": m.source_file,
            "tab": m.tab, "cell_ref": m.cell_ref,
            "validation_status": status, "variance_pct": vpct.get((m.metric_type, m.period)),
            "confidence": m.confidence if m.confidence is not None else _CONF.get(status, 1.0),
            "confirmed": True,
        })
    return rows


def ingest_files(paths: list, company: str = "Company", firm_id: str = DEFAULT_FIRM) -> dict:
    company_id = company_slug(company)
    paths = [Path(p) for p in paths]
    excels = [p for p in paths if p.suffix.lower() in (".xlsx", ".xls")]
    pdfs = [p for p in paths if p.suffix.lower() == ".pdf"]
    texts = [p for p in paths if p.suffix.lower() in (".txt", ".md")]

    pa_metrics: list[ExtractedMetric] = []   # all Pipeline A metrics (Excel + image PDF)
    chunks = []
    image_pdfs_ocred: list[str] = []
    text_pdfs: list[str] = []

    # --- Excel → numbers ---
    for x in excels:
        pa_metrics += extract_from_excel(x)

    # --- PDFs → text-layer narrative, OR image-only (both pipelines via one OCR pass) ---
    for pdf in pdfs:
        text_doc = load_pdf(pdf)                      # pdfplumber text layer
        if text_doc.pages:                            # has a text layer
            chunks += structural_chunks(text_doc)     # narrative → Pipeline B
            pa_metrics += extract_from_text_pdf(pdf)  # any financial TABLES → Pipeline A (deterministic)
            text_pdfs.append(pdf.name)
        else:                                         # image-only → OCR once, feed both
            img_metrics, pages_text = parse_image_pdf(pdf)
            pa_metrics += img_metrics
            ocr_doc = ocr_doc_from_pages(pdf, pages_text)
            if ocr_doc.pages:
                chunks += structural_chunks(ocr_doc)
            image_pdfs_ocred.append(pdf.name)

    # --- plain text → narrative ---
    for txt in texts:
        doc = load_text(txt)
        if doc.pages:
            chunks += structural_chunks(doc)

    # --- store numbers (validate + variance once over the combined set) ---
    metric_rows = _build_metric_rows(pa_metrics, company, company_id, firm_id)
    if metric_rows:
        store.store_metrics(metric_rows)

    # --- store narrative ---
    if chunks:
        embed_chunks(chunks)
        store.store_chunks(chunks, company_id=company_id, firm_id=firm_id)

    return {
        "company": company, "company_id": company_id,
        "metrics_stored": len(metric_rows),
        "pdfs_chunked": len({c.source_file for c in chunks}),
        "chunks_stored": len(chunks),
        "image_pdfs_ocred": image_pdfs_ocred,     # image PDFs run through OCR → both pipelines
        "text_pdfs": text_pdfs,
    }
