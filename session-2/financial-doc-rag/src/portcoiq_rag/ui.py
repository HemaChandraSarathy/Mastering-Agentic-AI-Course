"""Design tokens + embedded-HTML one-pager renderer for Streamlit.

The one-pager mirrors src/components/dashboard/InsightsPanel.tsx (CompanyInsightsView): a
vertical stack of linen-soft cards — header → 4 summary cards → Bottomline (sentiment) →
Key Metrics table → Variance Insights → Headwinds/Tailwinds → Data Sources.

IMPORTANT: st.components.v1.html renders in a sandboxed iframe, so the :root tokens MUST be
embedded in the returned HTML (the app-level CSS does not reach the iframe). render_onepager_html
therefore includes its own <style> with the verbatim tokens.
"""
from __future__ import annotations

import re

from .onepager import CompanyInsightData

# --- Design-system tokens (linen background, accent, type scale) -------------
ROOT_CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root {
  --color-ink:#0F1117; --color-ink-soft:#1A1D27;
  --color-linen:#F5F3EF; --color-linen-soft:#FAFAF8;
  --color-accent:#3A5F8A; --color-accent-light:#E8EEF5; --color-accent-dark:#274670;
  --color-neutral-900:#1C1C1E; --color-neutral-600:#6B6B6F; --color-neutral-400:#AEAEB2;
  --color-neutral-100:#E5E5EA; --color-neutral-50:#F2F2F7;
  --color-success:#2D7A5F; --color-success-light:#E6F2ED;
  --color-warning:#9A7B2F; --color-warning-light:#F4EDD5;
  --color-danger:#8B3A3A; --color-danger-light:#F2E6E6;
  --font-serif:'DM Serif Display',Georgia,serif;
  --font-sans:'DM Sans',-apple-system,sans-serif;
  --font-mono:'IBM Plex Mono','Courier New',monospace;
  --radius-lg:8px; --radius-xl:12px; --radius-sm:4px; --radius-pill:9999px;
}
"""

# Streamlit chrome (main page, not the iframe). Includes Canvas-tab styling so the
# Ingest tab is a canvas-style ingest UI: dashed drop zone, source cards, coverage.
APP_CSS = f"""
<style>
{ROOT_CSS}
.stApp {{ background: var(--color-linen); }}
h1,h2,h3 {{ font-family: var(--font-serif); color: var(--color-neutral-900); }}
html, body, [class*="css"] {{ font-family: var(--font-sans); }}

/* Canvas-style drop zone — restyle Streamlit's file uploader */
[data-testid="stFileUploaderDropzone"] {{
  border: 2px dashed var(--color-neutral-100); border-radius: var(--radius-xl);
  background: var(--color-linen-soft); transition: border-color 150ms;
}}
[data-testid="stFileUploaderDropzone"]:hover {{ border-color: var(--color-accent); }}

/* Canvas source cards */
.cc {{ background: var(--color-linen-soft); border: 0.5px solid var(--color-neutral-100);
  border-radius: var(--radius-lg); padding: 14px 16px; margin-bottom: 10px; }}
.cc-head {{ display: flex; align-items: center; gap: 8px; }}
.cc-name {{ font-weight: 600; font-size: 14px; color: var(--color-neutral-900); }}
.cc-badges {{ display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }}
.cc-badge {{ font-size: 10px; padding: 2px 8px; border-radius: var(--radius-pill);
  border: 0.5px solid var(--color-neutral-100); color: var(--color-neutral-600); }}
.cc-badge.cat {{ background: var(--color-accent-light); color: var(--color-accent); border-color: var(--color-accent-light); }}
.cc-meta {{ font-size: 11px; color: var(--color-neutral-400); margin-top: 8px; font-family: var(--font-mono); }}

/* Coverage tracker */
.cov {{ border-top: 0.5px solid var(--color-neutral-100); padding-top: 12px; margin-top: 6px; }}
.cov-head {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;
  font-size: 12px; font-weight: 500; color: var(--color-neutral-600); }}
.cov-bar {{ width: 120px; height: 6px; border-radius: var(--radius-pill);
  background: var(--color-neutral-100); overflow: hidden; }}
.cov-bar > div {{ height: 100%; background: var(--color-accent); }}
.cov-row {{ display: flex; align-items: center; gap: 8px; font-size: 12px; padding: 3px 0; }}
.cov-row .v {{ margin-left: auto; font-family: var(--font-mono); color: var(--color-neutral-600); }}
.cov-ok {{ color: var(--color-success); }} .cov-no {{ color: var(--color-neutral-400); }}
</style>
"""

# Styles embedded INTO the one-pager iframe.
_ONEPAGER_CSS = ROOT_CSS + """
*{box-sizing:border-box;}
body{margin:0;background:var(--color-linen);}
.wrap{font-family:var(--font-sans);color:var(--color-neutral-900);padding:6px 4px 24px;}
.hdr{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:16px;}
.hdr .name{font-family:var(--font-serif);font-size:22px;}
.pill{font-size:11px;padding:2px 10px;border-radius:var(--radius-pill);border:0.5px solid var(--color-neutral-100);color:var(--color-neutral-600);}
.banner{font-size:10px;color:var(--color-warning);background:var(--color-warning-light);padding:2px 8px;border-radius:var(--radius-sm);}
.grid{display:grid;gap:12px;margin-bottom:16px;}
.g3{grid-template-columns:repeat(3,1fr);}
.g2{grid-template-columns:repeat(2,1fr);}
.card{background:var(--color-linen-soft);border:0.5px solid var(--color-neutral-100);border-radius:var(--radius-lg);padding:16px 18px;margin-bottom:16px;}
.clabel{font-size:13px;font-weight:500;color:var(--color-neutral-600);}
.cnum{font-family:var(--font-mono);font-size:30px;font-weight:600;color:var(--color-neutral-900);line-height:1.15;}
.cnum.empty{color:var(--color-neutral-400);font-size:15px;}
.csub{font-family:var(--font-mono);font-size:15px;color:var(--color-neutral-600);}
.ctitle{font-family:var(--font-serif);font-size:16px;margin-bottom:10px;}
.ctitle.sm{font-size:14px;}
table{width:100%;border-collapse:collapse;font-size:13px;}
th{text-align:left;font-weight:500;padding:8px;border-bottom:0.5px solid var(--color-neutral-100);font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--color-neutral-400);}
td{padding:8px;border-bottom:0.5px solid var(--color-neutral-100);vertical-align:top;}
tr:last-child td{border-bottom:0;}
.r{text-align:right;}
.mono{font-family:var(--font-mono);}
.pos{color:var(--color-success);}.neg{color:var(--color-danger);}
.muted{color:var(--color-neutral-600);}
.badge{display:inline-block;font-size:10px;padding:2px 8px;border-radius:var(--radius-pill);border:0.5px solid var(--color-neutral-100);color:var(--color-neutral-600);}
ul.bul{margin:4px 0 0;padding:0;list-style:none;}
ul.bul li{font-size:13px;color:var(--color-neutral-600);margin:6px 0;padding-left:16px;position:relative;line-height:1.5;}
ul.bul li:before{content:'•';position:absolute;left:0;}
.src{display:flex;align-items:center;justify-content:space-between;padding:8px 10px;border-radius:var(--radius-sm);background:var(--color-neutral-50);margin:6px 0;font-size:13px;}
.variance{background:var(--color-accent-light);border-color:var(--color-accent);}
.vrow{display:flex;align-items:center;gap:8px;padding:8px 0;}
"""

_SENT = {"positive": ("var(--color-success)", "Positive"), "negative": ("var(--color-danger)", "Negative"),
         "mixed": ("var(--color-warning)", "Mixed"), "neutral": ("var(--color-neutral-400)", "Neutral")}
_FLAG = {"ok": ("var(--color-success)", "✓"), "warning": ("var(--color-warning)", "⚠"),
         "alert": ("var(--color-danger)", "●")}


def _qoq_class(s: str) -> str:
    return "pos" if s.strip().startswith("+") else ("neg" if s.strip().startswith("-") else "")


def _summary_card(label: str, value_html: str, sub_html: str = "") -> str:
    return (f'<div class="card" style="margin:0;"><div class="clabel">{label}</div>'
            f'<div style="margin-top:6px;">{value_html}</div>{sub_html}</div>')


def _file_icon(name: str) -> str:
    n = name.lower()
    if n.endswith((".xlsx", ".xls", ".csv")):
        return "📊"
    if n.endswith((".png", ".jpg", ".jpeg")):
        return "🖼"
    return "📄"


def source_card(name: str, doc_type: str | None, period: str | None,
                chunks: int = 0, metrics: int = 0) -> str:
    """One Canvas-style source card (mirrors CanvasSourceCard)."""
    badges = ""
    if doc_type:
        badges += f'<span class="cc-badge cat">{doc_type.replace("_", " ")}</span>'
    if period:
        badges += f'<span class="cc-badge">{period}</span>'
    meta = []
    if chunks:
        meta.append(f"{chunks} chunks")
    if metrics:
        meta.append(f"{metrics} metrics")
    return (f'<div class="cc"><div class="cc-head"><span>{_file_icon(name)}</span>'
            f'<span class="cc-name">{name}</span></div>'
            f'<div class="cc-badges">{badges}</div>'
            f'<div class="cc-meta">{" · ".join(meta) or "—"}</div></div>')


def coverage(rows: list[tuple[str, str | None]], label: str = "metrics") -> str:
    """Canvas-style coverage tracker. rows = [(metric_label, value_or_None)]."""
    covered = sum(1 for _, v in rows if v is not None)
    pct = int(covered / len(rows) * 100) if rows else 0
    items = ""
    for lbl, v in rows:
        if v is not None:
            items += (f'<div class="cov-row"><span class="cov-ok">✓</span><span>{lbl}</span>'
                      f'<span class="v">{v}</span></div>')
        else:
            items += f'<div class="cov-row"><span class="cov-no">○</span><span class="cov-no">{lbl}</span></div>'
    return (f'<div class="cov"><div class="cov-head"><span>{covered} of {len(rows)} {label} covered</span>'
            f'<div class="cov-bar"><div style="width:{pct}%"></div></div></div>{items}</div>')


def _is_sig_qoq(qoq: str) -> bool:
    num = re.sub(r"[^-\d.]", "", qoq or "")
    try:
        return bool(num) and abs(float(num)) > 10
    except ValueError:
        return False


def onepager_height(d: CompanyInsightData) -> int:
    """Estimate the rendered height so the iframe fits content (no inner scroll; page scrolls)."""
    n_metrics = len(d.metrics)
    n_winds = max(len(d.headwinds), len(d.tailwinds), 1)
    n_sources = len(d.dataSources)
    n_var = sum(1 for m in d.metrics if _is_sig_qoq(m.qoq))
    summary_lines = max(1, len(d.summary) // 85 + d.summary.count("\n") + 1)
    h = 90 + 150                       # header + summary-card grid
    h += 70 + summary_lines * 24       # bottomline
    h += 95 + n_metrics * 40           # key-metrics table
    h += (60 + n_var * 34) if n_var else 0   # variance card
    h += 85 + n_winds * 46             # headwinds/tailwinds
    h += 75 + n_sources * 42           # data sources
    h += 140                           # margins + slack
    return int(h)


_HERO_CSS = _ONEPAGER_CSS + """
.hwrap{max-width:980px;margin:0 auto;}
svg.i{display:block;}
.eyebrow{font-family:var(--font-mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--color-accent);}
.hero{text-align:center;padding:4px 8px 2px;}
.hero h1{font-family:var(--font-serif);font-size:50px;line-height:1.02;margin:10px 0 0;}
.hero .val{font-size:16px;color:var(--color-neutral-600);max-width:660px;margin:16px auto 0;line-height:1.6;}
.hero .val b{color:var(--color-neutral-900);}
.sample{display:inline-block;margin-top:16px;font-size:10px;color:var(--color-warning);background:var(--color-warning-light);padding:3px 12px;border-radius:var(--radius-pill);letter-spacing:.04em;}
.stats{display:grid;grid-template-columns:repeat(4,1fr);margin:30px 0 6px;border:0.5px solid var(--color-neutral-100);border-radius:var(--radius-xl);background:var(--color-linen-soft);overflow:hidden;}
.stat{padding:18px 10px;text-align:center;border-right:0.5px solid var(--color-neutral-100);}
.stat:last-child{border-right:0;}
.stat .num{font-family:var(--font-mono);font-size:26px;font-weight:600;color:var(--color-accent);}
.stat .lab{font-family:var(--font-mono);font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--color-neutral-400);margin-top:4px;}
.sec{margin:40px 0 16px;text-align:center;}
.sec .eyebrow{display:block;margin-bottom:4px;}
.sec h2{font-family:var(--font-serif);font-size:24px;margin:0;}
.why{position:relative;background:var(--color-accent-light);border-radius:var(--radius-xl);padding:22px 26px 22px 58px;font-size:14.5px;line-height:1.7;color:var(--color-neutral-900);}
.why .qm{position:absolute;left:18px;top:6px;font-family:var(--font-serif);font-size:48px;color:var(--color-accent);opacity:.45;}
.why b{color:var(--color-accent-dark);}
.flow{background:var(--color-linen-soft);border:0.5px solid var(--color-neutral-100);border-radius:var(--radius-xl);padding:22px;}
.fnode{display:flex;align-items:center;justify-content:center;gap:10px;background:#fff;border:0.5px solid var(--color-neutral-100);border-radius:var(--radius-lg);padding:11px 18px;max-width:430px;margin:0 auto;}
.fnode .nt{font-family:var(--font-mono);font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--color-neutral-400);}
.fnode .nb{font-size:13.5px;font-weight:500;}
.fic{color:var(--color-accent);}
.conn{width:1px;height:20px;background:var(--color-neutral-100);margin:9px auto 4px;position:relative;}
.conn:after{content:'';position:absolute;left:-3px;bottom:-1px;width:7px;height:7px;border-right:1px solid var(--color-neutral-400);border-bottom:1px solid var(--color-neutral-400);transform:rotate(45deg);}
.lanes{display:grid;grid-template-columns:1fr 1fr;gap:18px;}
.lane{border-radius:var(--radius-lg);overflow:hidden;border:0.5px solid var(--color-neutral-100);background:#fff;}
.lane .bar{height:3px;}
.lane.a .bar{background:var(--color-neutral-400);} .lane.b .bar{background:var(--color-accent);}
.lane .lhd{padding:12px 16px 9px;}
.lane .lh{font-family:var(--font-serif);font-size:16px;display:flex;align-items:center;gap:8px;}
.lane .ls{font-family:var(--font-mono);font-size:9px;letter-spacing:.08em;text-transform:uppercase;margin-top:3px;}
.lane.a .ls{color:var(--color-neutral-400);} .lane.b .ls{color:var(--color-accent);}
.lane.a .lh .fic{color:var(--color-neutral-600);}
.lstep{display:flex;align-items:center;gap:10px;padding:7px 16px;font-size:13px;border-top:0.5px solid var(--color-neutral-50);}
.lstep .si{flex:0 0 auto;width:24px;height:24px;border-radius:var(--radius-pill);display:flex;align-items:center;justify-content:center;background:var(--color-neutral-50);color:var(--color-neutral-600);}
.lane.b .lstep .si{background:var(--color-accent-light);color:var(--color-accent-dark);}
.gate{display:flex;align-items:center;justify-content:center;gap:10px;background:var(--color-warning-light);border:0.5px solid var(--color-warning);border-radius:var(--radius-lg);padding:12px 16px;font-size:13.5px;font-weight:500;}
.gate .fic{color:var(--color-warning);}
.out{display:flex;align-items:center;justify-content:center;gap:10px;background:var(--color-accent);border-radius:var(--radius-lg);padding:13px 16px;}
.out .nb{font-family:var(--font-serif);font-size:16px;color:#fff;}
.out .fic{color:#fff;}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}
.choice{background:var(--color-linen-soft);border:0.5px solid var(--color-neutral-100);border-left:2px solid var(--color-accent);border-radius:var(--radius-lg);padding:16px;}
.choice .cic{width:30px;height:30px;border-radius:var(--radius-md);background:var(--color-accent-light);color:var(--color-accent);display:flex;align-items:center;justify-content:center;margin-bottom:10px;}
.choice .ch{font-family:var(--font-serif);font-size:15px;margin-bottom:6px;}
.choice .cd{font-size:12px;color:var(--color-neutral-600);line-height:1.55;}
.outs{display:grid;grid-template-columns:repeat(2,1fr);gap:12px 24px;}
.outrow{display:flex;gap:10px;font-size:13.5px;line-height:1.5;align-items:flex-start;}
.outrow .oc{color:var(--color-success);flex:0 0 auto;margin-top:1px;}
.pcards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}
.pcard{background:var(--color-linen-soft);border:0.5px solid var(--color-neutral-100);border-radius:var(--radius-lg);padding:16px;text-align:center;}
.pcard .ps{font-family:var(--font-mono);font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:var(--color-neutral-400);}
.pcard .pn{font-family:var(--font-serif);font-size:17px;margin:5px 0;}
.pcard .pm{font-family:var(--font-mono);font-size:11px;color:var(--color-neutral-600);}
.techf{margin-top:38px;padding-top:18px;border-top:0.5px solid var(--color-neutral-100);text-align:center;}
.techf .tc{display:inline-flex;gap:8px;flex-wrap:wrap;justify-content:center;margin-top:10px;}
.techf .tchip{font-family:var(--font-mono);font-size:11px;color:var(--color-neutral-600);background:var(--color-neutral-50);padding:4px 10px;border-radius:var(--radius-sm);}
"""


def hero_html(entries: list[dict] | None = None) -> str:
    """Landing/hero infographic shown when 'All Companies' (Portfolio) is selected."""
    def ic(p, sz=16):
        return (f'<svg class="i" width="{sz}" height="{sz}" viewBox="0 0 24 24" fill="none" '
                f'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
                f'stroke-linejoin="round">{p}</svg>')
    I = {
        "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
        "grid": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
        "layers": '<path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/>',
        "check": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="M22 4 12 14.01l-3-3"/>',
        "trend": '<path d="M3 17l6-6 4 4 7-7"/><path d="M14 8h6v6"/>',
        "scissors": '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.1 15.9M14.5 14.5 20 20M8.1 8.1 12 12"/>',
        "db": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
        "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
        "sort": '<path d="M11 5h10M11 9h7M11 13h4M3 17l3 3 3-3M6 18V4"/>',
        "quote": '<path d="M7 8H4a1 1 0 0 0-1 1v4a1 1 0 0 0 1 1h2v3H4M17 8h-3a1 1 0 0 0-1 1v4a1 1 0 0 0 1 1h2v3h-2"/>',
        "user": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
        "doc": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M9 13h6M9 17h6"/>',
        "split": '<path d="M16 3h5v5M21 3l-7 7M8 21H3v-5M3 21l7-7"/>',
        "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>',
        "building": '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4M9 6h.01M15 6h.01M9 10h.01M15 10h.01"/>',
    }

    def lstep(icon, text):
        return f'<div class="lstep"><span class="si">{ic(I[icon], 13)}</span><span>{text}</span></div>'

    laneA = ('<div class="lane a"><div class="bar"></div><div class="lhd">'
             f'<div class="lh"><span class="fic">{ic(I["grid"], 17)}</span>Pipeline A — Numbers</div>'
             '<div class="ls">deterministic · no embeddings</div></div>'
             + lstep("grid", "Extract tables (pdfplumber / pandas)")
             + lstep("layers", "Map to canonical taxonomy")
             + lstep("check", "Validate &amp; reconcile")
             + lstep("trend", "Variance vs prior period") + '</div>')
    laneB = ('<div class="lane b"><div class="bar"></div><div class="lhd">'
             f'<div class="lh"><span class="fic">{ic(I["search"], 17)}</span>Pipeline B — Narrative</div>'
             '<div class="ls">retrieval-augmented</div></div>'
             + lstep("scissors", "Chunk (semantic)")
             + lstep("db", "Embed → pgvector")
             + lstep("search", "Hybrid retrieve (dense + BM25)")
             + lstep("sort", "Rerank (cross-encoder)")
             + lstep("quote", "Cite — refusal-first") + '</div>')

    stats = [("2", "Pipelines"), ("38+", "Metrics mapped"), ("100%", "Cited"), ("Minutes", "Time to brief")]
    stats_html = "".join(f'<div class="stat"><div class="num">{n}</div><div class="lab">{l}</div></div>'
                         for n, l in stats)

    choices = [
        ("split", "Two pipelines, not one", "Numbers extracted deterministically; RAG reserved for the narrative ‘why.’ Tables never go through retrieval."),
        ("grid", "Deterministic numbers", "Table parse → taxonomy map → reconciliation (net = pretax − tax) → variance. Exact, traceable, self-checked."),
        ("search", "Hybrid retrieval + rerank", "Dense (pgvector) + BM25 + RRF + period filter, then a FlashRank cross-encoder. Refusal-first."),
        ("user", "Human confirm gate", "The analyst reviews and edits extracted figures before they reach the brief — never a blank form."),
        ("shield", "Provenance + confidence", "Every figure cites its source cell, as-of period, and a confidence score. Every claim cites [S#]."),
        ("building", "Multi-tenant by design", "company_id + firm_id on every row; company-filtered vector search — the production multi-portco schema."),
    ]
    choice_cards = "".join(
        f'<div class="choice"><div class="cic">{ic(I[icn], 16)}</div><div class="ch">{h}</div>'
        f'<div class="cd">{d}</div></div>' for icn, h, d in choices)

    outs = ["Exact, reconciled financials with cell-level provenance",
            "Quarter-over-quarter variance flagged automatically",
            "A cited first-draft Insights one-pager",
            "Grounded Q&amp;A that refuses when the answer isn't in the docs"]
    outs_html = "".join(f'<div class="outrow"><span class="oc">{ic(I["check"], 15)}</span>'
                        f'<span>{o}</span></div>' for o in outs)

    tech = ["Supabase pgvector", "Nebius embeddings", "Claude", "FlashRank", "LangGraph", "Streamlit"]
    tech_html = "".join(f'<span class="tchip">{t}</span>' for t in tech)

    strip = ""
    if entries:
        cards = "".join(
            f'<div class="pcard"><div class="ps">{e.get("sector","")}</div>'
            f'<div class="pn">{e["name"]}</div>'
            f'<div class="pm">{e.get("docs",0)} docs · {e.get("metrics",0)} metrics</div></div>'
            for e in entries)
        strip = ('<div class="sec"><span class="eyebrow">Sample data</span><h2>Your portfolio</h2></div>'
                 f'<div class="pcards">{cards}</div>'
                 '<div style="text-align:center;margin-top:14px;" class="muted">↑ Pick a company in the '
                 'sidebar to open its workspace.</div>')

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_HERO_CSS}</style></head>
<body><div class="wrap hwrap">
  <div class="hero">
    <div class="eyebrow">Portfolio Document Intelligence</div>
    <h1>From document chaos<br>to a cited brief</h1>
    <div class="val">Drop a portfolio company's messy Excel, board-pack PDFs and earnings transcripts —
      get back a <b>cited, analyst-confirmed Insights one-pager</b> and grounded Q&amp;A, in minutes.</div>
    <div class="sample">● Demo on fabricated sample companies — not customer data</div>
  </div>

  <div class="stats">{stats_html}</div>

  <div class="sec"><span class="eyebrow">The thesis</span><h2>Why it's built this way</h2></div>
  <div class="why"><span class="qm">“</span>Most tools answer financial questions with RAG — but embedding
    retrieval over financial <b>tables</b> is lossy: rows and headers split across chunks, so “what was
    revenue?” comes back fragmented or wrong. We split the problem — <b>deterministic extraction for the
    numbers</b> (exact, reconciled, traceable) and <b>RAG for the narrative “why.”</b> The failure mode
    other pipelines spend their whole project fighting, ours avoids by design.</div>

  <div class="sec"><span class="eyebrow">Under the hood</span><h2>How it works</h2></div>
  <div class="flow">
    <div class="fnode"><span class="fic">{ic(I["file"], 18)}</span>
      <div><div class="nt">Ingest</div><div class="nb">Documents — Excel · PDF · transcripts</div></div></div>
    <div class="conn"></div>
    <div class="lanes">{laneA}{laneB}</div>
    <div class="conn"></div>
    <div class="gate"><span class="fic">{ic(I["user"], 17)}</span>Human review &amp; confirm — analyst edits / approves the figures</div>
    <div class="conn"></div>
    <div class="out"><span class="fic">{ic(I["doc"], 18)}</span><span class="nb">Cited Insights one-pager + grounded Q&amp;A</span></div>
  </div>

  <div class="sec"><span class="eyebrow">Design</span><h2>Architectural choices</h2></div>
  <div class="cards">{choice_cards}</div>

  <div class="sec"><span class="eyebrow">Outcomes</span><h2>What you get</h2></div>
  <div class="outs">{outs_html}</div>

  {strip}

  <div class="techf"><span class="eyebrow">Built on</span><div class="tc">{tech_html}</div></div>
</div></body></html>"""


def portfolio_html(entries: list[dict]) -> str:
    """Portfolio overview ('All Companies'). entries = [{name, sector, headline:[(lbl,val)],
    docs, metrics}]."""
    cards = ""
    for e in entries:
        rows = "".join(
            f'<div style="display:flex;justify-content:space-between;font-size:12px;margin:3px 0;">'
            f'<span class="muted">{lbl}</span><span class="mono">{val}</span></div>'
            for lbl, val in e.get("headline", []))
        sector = f'<span class="pill">{e["sector"]}</span>' if e.get("sector") else ""
        cards += (f'<div class="card" style="margin:0;">'
                  f'<div style="font-family:var(--font-serif);font-size:17px;">{e["name"]}</div>'
                  f'<div style="margin:6px 0;">{sector}</div>{rows}'
                  f'<div class="cc-meta">{e.get("docs",0)} docs · {e.get("metrics",0)} metrics</div></div>')
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{_ONEPAGER_CSS}</style></head>'
            f'<body><div class="wrap"><div class="grid g3">{cards}</div></div></body></html>')


def render_onepager_html(d: CompanyInsightData) -> str:
    # ---- summary cards (honest empty states where the corpus lacks data) ----
    if d.latestMark:
        mark = (f'<span class="cnum">${d.latestMark["value"]:,.0f}M</span> '
                f'<span class="csub">@ {d.latestMark.get("multiple", 0)}x</span>')
    else:
        mark = '<span class="cnum empty">No valuation mark in source</span>'
    exitr = (f'<span class="cnum">{d.exitReadiness["score"]}%</span>' if d.exitReadiness
             else '<span class="cnum empty">No exit data in source</span>')
    dq = d.dataQuality
    gaps_badge = (f'<span class="badge" style="color:var(--color-warning);">{len(dq["gaps"])} gaps</span>'
                  if dq["gaps"] else '<span class="badge" style="color:var(--color-success);">Complete</span>')
    dq_html = (f'<span class="cnum">{dq["docsAvailable"]}/{dq["docsExpected"]}</span> '
               f'<span class="csub">docs</span>')
    dq_sub = f'<div style="margin-top:8px;">{gaps_badge} <span class="muted" style="font-size:11px;">Last: {dq["lastUpdated"]}</span></div>'

    cards = (f'<div class="grid g3">'
             f'{_summary_card("Latest Mark", mark)}'
             f'{_summary_card("Exit Readiness", exitr)}'
             f'{_summary_card("Data Quality", dq_html, dq_sub)}'
             f'</div>')

    # ---- bottomline ----
    sent_color, sent_label = _SENT.get(d.sentiment, _SENT["neutral"])
    sent_badge = (f'<span class="badge" style="color:{sent_color};border-color:{sent_color};">'
                  f'{sent_label}</span>')
    summary = d.summary or ('<span class="muted">No narrative yet — click “Generate cited narrative.”</span>')
    bottomline = (f'<div class="card"><div class="ctitle">💡 Bottomline &nbsp;{sent_badge}</div>'
                  f'<div style="font-size:13px;line-height:1.65;">{summary}</div></div>')

    # ---- key metrics table ----
    def _conf_html(c):
        if c is None:
            return '<span class="muted">—</span>'
        col = ("var(--color-success)" if c >= 0.8 else
               "var(--color-warning)" if c >= 0.5 else "var(--color-danger)")
        return f'<span style="color:{col};">{c*100:.0f}%</span>'

    rows = ""
    for m in d.metrics:
        fc, fi = _FLAG[m.flag]
        rows += (f'<tr><td style="font-weight:500;">{m.name}</td>'
                 f'<td class="r mono">{m.value}</td>'
                 f'<td class="r mono {_qoq_class(m.qoq)}">{m.qoq}</td>'
                 f'<td><span style="color:{fc};">{fi}</span></td>'
                 f'<td class="r mono" style="font-size:11px;">{_conf_html(m.confidence)}</td>'
                 f'<td class="mono muted" style="font-size:10px;">{m.recency or ""}</td>'
                 f'<td class="mono muted" style="font-size:10px;">{m.provenance or ""}</td></tr>')
    metrics_card = (f'<div class="card"><div class="ctitle">Key Metrics</div>'
                    f'<table><thead><tr><th>Metric</th><th class="r">Value</th><th class="r">QoQ</th>'
                    f'<th>Status</th><th class="r">Conf.</th><th>As of</th><th>Source</th></tr></thead>'
                    f'<tbody>{rows}</tbody></table></div>')

    # ---- variance insights (|QoQ| > 10%) ----
    variance_card = ""
    sig = []
    for m in d.metrics:
        num = re.sub(r"[^-\d.]", "", m.qoq)
        if num and abs(float(num)) > 10:
            sig.append(m)
    if sig:
        vrows = ""
        for m in sig:
            neg = m.qoq.strip().startswith("-")
            badge_c = "var(--color-danger)" if neg else "var(--color-success)"
            vrows += (f'<div class="vrow"><span style="font-weight:500;font-size:13px;">{m.name}</span>'
                      f'<span class="badge" style="color:{badge_c};border-color:{badge_c};">{m.qoq} QoQ</span>'
                      f'<span class="muted" style="font-size:12px;">What\'s driving this '
                      f'{"decline" if neg else "improvement"}?</span></div>')
        variance_card = (f'<div class="card variance"><div class="ctitle" style="color:var(--color-accent);">'
                         f'💡 Variance Insights Needed</div>{vrows}</div>')

    # ---- headwinds / tailwinds ----
    def _ul(items):
        return '<ul class="bul">' + "".join(f"<li>{x}</li>" for x in items) + "</ul>" if items else \
               '<span class="muted" style="font-size:12px;">—</span>'
    winds = (f'<div class="grid g2">'
             f'<div class="card" style="margin:0;"><div class="ctitle sm" style="color:var(--color-danger);">Headwinds</div>{_ul(d.headwinds)}</div>'
             f'<div class="card" style="margin:0;"><div class="ctitle sm" style="color:var(--color-success);">Tailwinds</div>{_ul(d.tailwinds)}</div>'
             f'</div>')

    # ---- data sources ----
    srcs = ""
    for s in d.dataSources:
        right = (f'<span class="badge">{s.metrics} metrics</span>' if s.status == "current"
                 else '<span class="badge" style="color:var(--color-warning);">MISSING</span>')
        icon = "📄" if s.type == "document" else "🎙"
        srcs += f'<div class="src"><span>{icon}&nbsp; {s.name}</span>{right}</div>'
    avail_badge = f'<span class="badge">{dq["docsAvailable"]}/{dq["docsExpected"]} available</span>'
    sources_card = (f'<div class="card"><div class="ctitle">Data Sources &nbsp;{avail_badge}</div>{srcs}</div>')

    sector_pill = f'<span class="pill">{d.sector}</span>' if d.sector else ""
    note_banner = f'<span class="banner">{d.note}</span>' if d.note else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_ONEPAGER_CSS}</style></head>
<body><div class="wrap">
  <div class="hdr">
    <span class="name">{d.company}</span>
    {sector_pill}
    <span class="pill">{d.period}</span>
    <span class="muted" style="font-size:12px;">Updated {d.generatedAt}</span>
    {note_banner}
  </div>
  {cards}
  {bottomline}
  {metrics_card}
  {variance_card}
  {winds}
  {sources_card}
</div></body></html>"""
