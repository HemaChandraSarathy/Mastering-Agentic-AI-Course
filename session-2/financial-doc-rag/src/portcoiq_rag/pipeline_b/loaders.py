"""Load narrative docs (text PDFs) into per-page text + metadata.

Quarterly-report PDFs are image-only (handled by Pipeline A via the Excel); the narrative
docs (transcripts, analyst reports) have real text layers, so pdfplumber reads them directly.
PNG news releases would need OCR/vision — out of scope for this no-keys pass.
"""
from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from ..pipeline_a.models import parse_period

# folder name -> canonical doc_type
DOC_TYPE_BY_FOLDER = {
    "earnings transcript": "earnings_transcript",
    "analyst reports": "analyst_report",
    "news releases": "news_release",
    "quarterly reports": "quarterly_report",
}


def detect_doc_type(path: Path) -> str | None:
    folder = path.parent.name.lower()
    if folder in DOC_TYPE_BY_FOLDER:
        return DOC_TYPE_BY_FOLDER[folder]
    name = path.name.lower()
    if "transcript" in name:
        return "earnings_transcript"
    if "report" in name and "quarterly" not in name:
        return "analyst_report"
    return None


# Running headers/footers + watermarks that repeat on most pages and add noise.
_BOILERPLATE = [
    re.compile(r"REFINITIV STREETEVENTS", re.I),
    re.compile(r"www\.refinitiv\.com", re.I),
    re.compile(r"\bContact Us\b", re.I),
    re.compile(r"©\s*\d{4}\s*Refinitiv", re.I),
    re.compile(r"COP\.N\s*-\s*Q\d.*Earnings Call\s*$", re.I),   # repeated date/time page header
    re.compile(r"^\s*\d{1,3}\s*$"),                              # bare page numbers
    re.compile(r"©\s*\d{4}\s*Argus Research", re.I),
]


def _clean(text: str) -> str:
    # The ARGUS report renders every glyph 4x ('CCCCOOOONNNN...' = 'CON...'). Collapse any
    # run of 3+ identical chars to one — safe for English (no word has 3 in a row) and for
    # the transcripts (only affects '...'/'---'), but un-garbles the quadrupled doc.
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    # then collapse any remaining repeated-substring watermark and drop boilerplate lines.
    text = re.sub(r"(.{6,40}?)\1{2,}", r"\1", text)
    kept = []
    for line in text.splitlines():
        if any(p.search(line) for p in _BOILERPLATE):
            continue
        kept.append(line)
    text = "\n".join(kept)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class LoadedDoc:
    def __init__(self, path: Path):
        self.path = path
        self.source_file = path.name
        self.doc_type = detect_doc_type(path)
        self.period = parse_period(path.stem)        # 'Q3 2025 Earnings Transcript' -> 'Q3 2025'
        self.company = None                          # company is derived from metrics, not the doc
        self.pages: list[tuple[int, str]] = []       # (page_no, text)

    @property
    def full_text(self) -> str:
        return "\n\n".join(t for _, t in self.pages)


def load_pdf(path: str | Path) -> LoadedDoc:
    path = Path(path)
    doc = LoadedDoc(path)
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            raw = page.extract_text() or ""
            cleaned = _clean(raw)
            if cleaned:
                doc.pages.append((i + 1, cleaned))
    return doc


def load_text(path: str | Path) -> LoadedDoc:
    """Load a plain-text / markdown narrative doc (one page)."""
    path = Path(path)
    doc = LoadedDoc(path)
    text = _clean(path.read_text(encoding="utf-8", errors="ignore"))
    if text:
        doc.pages.append((1, text))
    return doc


def ocr_doc_from_pages(path: str | Path, pages_text: list[tuple[int, str]]) -> LoadedDoc:
    """Build a narrative LoadedDoc from LiteParse OCR page text (image-only PDF).

    Lets an image-only PDF feed Pipeline B (narrative chunks) off the same OCR pass that
    Pipeline A uses for numbers — board packs carry commentary alongside the tables.
    """
    path = Path(path)
    doc = LoadedDoc(path)
    for pno, raw in pages_text:
        cleaned = _clean(raw or "")
        if cleaned:
            doc.pages.append((pno, cleaned))
    return doc


def load_corpus(corpus_dir: str | Path, doc_types: set[str] | None = None) -> list[LoadedDoc]:
    """Load all text PDFs under a corpus dir, optionally filtered to certain doc_types."""
    corpus_dir = Path(corpus_dir)
    docs: list[LoadedDoc] = []
    for path in sorted(corpus_dir.rglob("*")):
        ext = path.suffix.lower()
        if ext == ".pdf":
            d = load_pdf(path)
        elif ext in (".txt", ".md"):
            d = load_text(path)
        else:
            continue
        if not d.pages:                 # image-only (e.g. quarterly reports) — skip here
            continue
        if doc_types and d.doc_type not in doc_types:
            continue
        docs.append(d)
    return docs
