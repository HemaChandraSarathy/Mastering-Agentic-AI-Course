-- financial-doc-rag — RAG tables on a shared Supabase project.
-- Isolated from any production tables (rag_* prefix). Apply via:
--   supabase db execute --file db/0001_rag_tables.sql      (or psql / SQL editor)
--
-- EMBEDDING DIMENSION: the vector(...) dim below MUST equal your Nebius embedding
-- model's output dim (NEBIUS_EMBED_DIM in .env). IMPORTANT pgvector constraint:
--   * `vector` HNSW/IVFFlat indexes support at most 2000 dimensions.
--   * If your model is >2000 dims (e.g. bge-en-icl = 4096), either pick a <=1024-dim
--     model (simplest) OR switch the column to halfvec(<=4000) + halfvec_cosine_ops.
-- This migration assumes a 1024-dim model. Change :DIM in both the column and index.

create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- Documents (one row per ingested source file)
-- ---------------------------------------------------------------------------
create table if not exists rag_documents (
    id          uuid primary key default gen_random_uuid(),
    company     text,
    doc_type    text,                 -- earnings_transcript | analyst_report | news_release | quarterly_report
    period      text,                 -- 'Qn YYYY' if known
    source_file text not null,
    page_count  int,
    created_at  timestamptz not null default now(),
    unique (source_file)
);

-- ---------------------------------------------------------------------------
-- Narrative chunks (Pipeline B) — dense + sparse retrieval
-- ---------------------------------------------------------------------------
create table if not exists rag_chunks (
    id           uuid primary key default gen_random_uuid(),
    document_id  uuid references rag_documents(id) on delete cascade,
    content      text not null,
    embedding    vector(1024),                       -- <-- match NEBIUS_EMBED_DIM
    company      text,
    doc_type     text,
    period       text,
    source_file  text,
    page         int,
    section      text,
    strategy     text not null default 'fixed',      -- 'fixed' | 'structural'
    chunk_index  int,
    content_tsv  tsvector generated always as (to_tsvector('english', content)) stored,
    created_at   timestamptz not null default now()
);

-- dense (cosine) — HNSW; requires dim <= 2000
create index if not exists rag_chunks_embedding_hnsw
    on rag_chunks using hnsw (embedding vector_cosine_ops);

-- sparse (BM25-ish) full-text
create index if not exists rag_chunks_content_tsv_gin
    on rag_chunks using gin (content_tsv);

create index if not exists rag_chunks_strategy_idx on rag_chunks (strategy);
create index if not exists rag_chunks_doc_period_idx on rag_chunks (doc_type, period);

-- ---------------------------------------------------------------------------
-- Confirmed metrics (Pipeline A) — deterministic numbers + provenance
-- ---------------------------------------------------------------------------
create table if not exists rag_metrics (
    id                uuid primary key default gen_random_uuid(),
    company           text,
    metric_type       text not null,                 -- canonical taxonomy key
    raw_label         text,
    period            text not null,
    value             double precision not null,
    unit              text,
    source_file       text,
    tab               text,
    cell_ref          text,                          -- provenance, e.g. 'Income Statement!E11'
    validation_status text default 'ok',             -- ok | warning | error
    variance_pct      double precision,
    confirmed         boolean not null default false, -- set true at the human confirm gate
    created_at        timestamptz not null default now(),
    unique (company, metric_type, period, source_file)
);

create index if not exists rag_metrics_company_period_idx on rag_metrics (company, period);

-- ---------------------------------------------------------------------------
-- RLS — enable; service-role key (used by this app) bypasses RLS. Add explicit
-- policies here if you ever expose these to anon/auth roles.
-- ---------------------------------------------------------------------------
alter table rag_documents enable row level security;
alter table rag_chunks    enable row level security;
alter table rag_metrics   enable row level security;

-- ---------------------------------------------------------------------------
-- Grants — with "auto-expose new tables" DISABLED, new tables aren't granted to
-- the API roles automatically. We use the service_role (secret) key, so grant it
-- explicitly. (service_role also bypasses RLS, so the policies above don't block it.)
-- ---------------------------------------------------------------------------
grant usage on schema public to service_role;
grant all privileges on rag_documents, rag_chunks, rag_metrics to service_role;

-- ---------------------------------------------------------------------------
-- Vector search RPC — callable via PostgREST (supabase.rpc). The embedding is
-- passed as a text literal like '[0.1,0.2,...]' and cast to vector inside, which
-- avoids JSON-array→vector coercion issues over the Data API.
-- ---------------------------------------------------------------------------
create or replace function match_rag_chunks(query_embedding text, match_count int default 8)
returns table (
    id uuid, content text, source_file text, page int,
    section text, period text, doc_type text, similarity float
)
language sql stable as $$
    select c.id, c.content, c.source_file, c.page, c.section, c.period, c.doc_type,
           1 - (c.embedding <=> query_embedding::vector) as similarity
    from rag_chunks c
    where c.embedding is not null
    order by c.embedding <=> query_embedding::vector
    limit match_count;
$$;

grant execute on function match_rag_chunks(text, int) to service_role;
