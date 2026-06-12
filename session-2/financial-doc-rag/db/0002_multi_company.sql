-- 0002 — Multi-company / multi-tenant scoping + transparency fields.
-- Run in the Supabase SQL editor after 0001.
--
-- MULTI-TENANT MAPPING (why these columns exist):
--   company_id  → in a multi-tenant deployment this is a UUID FK to portfolio_companies(id). Here it's a slug
--                 (e.g. 'meridian') so the demo is self-contained; the query pattern is identical.
--   firm_id     → tenant key. In a multi-tenant deployment a firm sees ONLY its own rows, enforced by an RLS policy
--                 like:  USING (firm_id = current_setting('request.jwt.claims')::json->>'firm_id').
--                 Here it defaults to 'demo-firm' (single tenant) — the column is the seam RLS sits on.
--   confidence  → extraction confidence (0..1); supports a "show source, recency, confidence" UI.

alter table rag_documents add column if not exists company_id text;
alter table rag_documents add column if not exists firm_id text default 'demo-firm';
alter table rag_chunks    add column if not exists company_id text;
alter table rag_chunks    add column if not exists firm_id text default 'demo-firm';
alter table rag_metrics   add column if not exists company_id text;
alter table rag_metrics   add column if not exists firm_id text default 'demo-firm';
alter table rag_metrics   add column if not exists confidence double precision default 1.0;

create index if not exists rag_chunks_company_idx  on rag_chunks  (company_id);
create index if not exists rag_metrics_company_idx on rag_metrics (company_id);
create index if not exists rag_documents_company_idx on rag_documents (company_id);

-- Company-filtered vector search. company_filter = NULL → search across all companies (portfolio).
-- (In a multi-tenant deployment, RLS additionally scopes this to the caller's firm; company_filter becomes company_id.)
drop function if exists match_rag_chunks(text, int);
create or replace function match_rag_chunks(
    query_embedding text,
    match_count int default 8,
    company_filter text default null
)
returns table (
    id uuid, content text, source_file text, page int,
    section text, period text, doc_type text, company_id text, similarity float
)
language sql stable as $$
    select c.id, c.content, c.source_file, c.page, c.section, c.period, c.doc_type, c.company_id,
           1 - (c.embedding <=> query_embedding::vector) as similarity
    from rag_chunks c
    where c.embedding is not null
      and (company_filter is null or c.company_id = company_filter)
    order by c.embedding <=> query_embedding::vector
    limit match_count;
$$;

grant execute on function match_rag_chunks(text, int, text) to service_role;
