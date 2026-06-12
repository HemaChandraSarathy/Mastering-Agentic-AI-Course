"""Persist + read chunks/metrics in Supabase pgvector, scoped by company (multi-tenant-shaped).

`company_id` is a slug here; in a multi-tenant deployment it maps to a portfolio_companies FK, and `firm_id`
maps to an RLS-enforced tenant key (see db/0002_multi_company.sql).
"""
from __future__ import annotations

from ..clients import supabase_client
from .models import Chunk
from .retrieve import Hit

DEFAULT_FIRM = "demo-firm"
_ALL = "00000000-0000-0000-0000-000000000000"  # sentinel: neq matches every real row


def _vec(emb: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in emb) + "]"


def _maybe_company(query, company_id: str | None):
    return query.eq("company_id", company_id) if company_id else query


# --- writes ----------------------------------------------------------------
def store_chunks(chunks: list[Chunk], company_id: str, firm_id: str = DEFAULT_FIRM,
                 replace: bool = True) -> int:
    sb = supabase_client()
    by_file: dict[str, list[Chunk]] = {}
    for c in chunks:
        by_file.setdefault(c.source_file, []).append(c)
    total = 0
    for source_file, cs in by_file.items():
        first = cs[0]
        doc = sb.table("rag_documents").upsert(
            {"company": first.company, "company_id": company_id, "firm_id": firm_id,
             "doc_type": first.doc_type, "period": first.period, "source_file": source_file,
             "page_count": max((c.page or 0) for c in cs)},
            on_conflict="source_file",
        ).execute()
        doc_id = doc.data[0]["id"]
        if replace:
            sb.table("rag_chunks").delete().eq("source_file", source_file).execute()
        rows = [{
            "document_id": doc_id, "content": c.content,
            "embedding": _vec(c.embedding) if c.embedding else None,
            "company": c.company, "company_id": company_id, "firm_id": firm_id,
            "doc_type": c.doc_type, "period": c.period, "source_file": c.source_file,
            "page": c.page, "section": c.section, "strategy": c.strategy, "chunk_index": c.chunk_index,
        } for c in cs]
        for i in range(0, len(rows), 100):
            sb.table("rag_chunks").insert(rows[i:i + 100]).execute()
        total += len(rows)
    return total


def store_metrics(rows: list[dict]) -> int:
    """Upsert metric rows (each already carries company_id, firm_id, confidence)."""
    sb = supabase_client()
    for i in range(0, len(rows), 100):
        sb.table("rag_metrics").upsert(
            rows[i:i + 100], on_conflict="company,metric_type,period,source_file"
        ).execute()
    return len(rows)


# --- reads (company-scoped) ------------------------------------------------
def list_companies() -> list[dict]:
    """Distinct companies present in the data: [{company_id, company}]."""
    sb = supabase_client()
    rows = (sb.table("rag_metrics").select("company_id, company").execute().data or [])
    rows += (sb.table("rag_documents").select("company_id, company").execute().data or [])
    seen: dict[str, str] = {}
    for r in rows:
        cid = r.get("company_id")
        if cid and cid not in seen:
            seen[cid] = r.get("company") or cid
    return [{"company_id": cid, "company": name} for cid, name in sorted(seen.items(), key=lambda x: x[1])]


def list_documents(company_id: str | None = None) -> list[dict]:
    sb = supabase_client()
    q = sb.table("rag_documents").select("source_file, doc_type, period, page_count, company_id, created_at")
    return _maybe_company(q, company_id).order("created_at").execute().data or []


def counts(company_id: str | None = None) -> dict:
    sb = supabase_client()
    d = _maybe_company(sb.table("rag_documents").select("id", count="exact"), company_id).execute()
    c = _maybe_company(sb.table("rag_chunks").select("id", count="exact"), company_id).execute()
    m = _maybe_company(sb.table("rag_metrics").select("id", count="exact"), company_id).execute()
    return {"documents": d.count or 0, "chunks": c.count or 0, "metrics": m.count or 0}


def load_chunks(company_id: str | None = None) -> list[Chunk]:
    sb = supabase_client()
    rows, page, size = [], 0, 1000
    while True:
        q = sb.table("rag_chunks").select(
            "content, source_file, page, section, period, doc_type, chunk_index, strategy, company_id")
        res = _maybe_company(q, company_id).range(page * size, page * size + size - 1).execute()
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < size:
            break
        page += 1
    return [Chunk(content=r["content"], source_file=r.get("source_file") or "", page=r.get("page"),
                  section=r.get("section"), period=r.get("period"), doc_type=r.get("doc_type"),
                  chunk_index=r.get("chunk_index") or 0, strategy=r.get("strategy") or "structural",
                  company=r.get("company_id")) for r in rows]


def load_metrics(company_id: str | None = None) -> list[dict]:
    sb = supabase_client()
    return _maybe_company(sb.table("rag_metrics").select("*"), company_id).execute().data or []


def clear_all() -> None:
    sb = supabase_client()
    sb.table("rag_chunks").delete().neq("id", _ALL).execute()
    sb.table("rag_documents").delete().neq("id", _ALL).execute()
    sb.table("rag_metrics").delete().neq("id", _ALL).execute()


class SupabaseDenseRetriever:
    """Dense retrieval via the pgvector RPC, optionally scoped to one company."""

    def __init__(self, company_id: str | None = None):
        self.sb = supabase_client()
        self.company_id = company_id

    def search(self, query: str, k: int = 8) -> list[Hit]:
        from .embed import embed_query
        vec = _vec(embed_query(query))
        res = self.sb.rpc("match_rag_chunks", {
            "query_embedding": vec, "match_count": k, "company_filter": self.company_id,
        }).execute()
        hits: list[Hit] = []
        for r in res.data or []:
            ch = Chunk(content=r["content"], source_file=r.get("source_file") or "",
                       page=r.get("page"), section=r.get("section"), period=r.get("period"),
                       doc_type=r.get("doc_type"), company=r.get("company_id"), strategy="structural")
            hits.append(Hit(chunk=ch, score=float(r.get("similarity") or 0.0)))
        return hits
