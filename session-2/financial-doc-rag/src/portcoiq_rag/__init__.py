"""financial-doc-rag — Financial Document Intelligence pipeline (Week 2 RAG project).

Two pipelines:
  - pipeline_a: deterministic numeric extraction → validation → variance (NO embeddings)
  - pipeline_b: narrative RAG (chunk → embed → retrieve → rerank)
Wired together in graph.py behind a human review/confirm gate, assembled into a
CompanyInsightData one-pager (onepager.py).
"""

__version__ = "0.1.0"
