# Eval report — A/B/C pipeline comparison

_Fictional Meridian sample. Custom LLM-judge metrics (RAGAS-equivalent; the `ragas` package is skipped to avoid langchain/Python-3.14 conflicts)._


Corpus: 5 narrative docs · fixed=9 chunks · semantic=31 chunks · 10 ground-truth questions.


| Metric | A: Fixed (no rerank) | B: Semantic (no rerank) | C: Semantic + Rerank |
|---|---|---|---|
| Faithfulness | 1.000 | 0.700 | 0.586 |
| Context Precision | 0.292 | 0.633 | 0.583 |
| Context Recall | 0.817 | 0.600 | 0.550 |

## Takeaways

- **Semantic chunking lifts precision 0.29 → 0.63 vs fixed-size** — the course's core chunking finding reproduces: keeping related sentences together produces cleaner retrieved context. (Fixed-size keeps the highest recall, 0.82, but the lowest precision, 0.29 — it grabs the right snippet *and* a lot of noise, yet still answers faithfully at 1.00.)

- **Reranking was roughly neutral here (0.63 → 0.58):** on a small, already-clean semantic candidate set, reranking top-6 → top-3 occasionally drops a relevant chunk. Cross-encoder reranking pays off more as the candidate pool gets larger and noisier — and its calibrated FlashRank scores give a better refusal signal regardless.

- Unlike the course's 10-K result (semantic vs fixed, 0.00 → 0.95), the dramatic chunking gap does NOT reproduce here — our corpus is small narrative text, and crucially financial **tables never hit RAG** in our design (Pipeline A extracts numbers deterministically). The fixed-chunking failure mode the course spends the whole project fixing is exactly what our two-pipeline architecture avoids.


## Refusal (unanswerable questions, config C)

| Q | refused? |
|---|---|
| R1: What was Meridian's revenue in 2019? | ✅ refused |
| R2: Who is Meridian's largest customer by name? | ✅ refused |
| R3: What is the CEO's annual compensation? | ✅ refused |

**Refusal accuracy: 3/3**


## Notes

- Numeric questions (revenue, EBITDA, leverage…) are answered by **Pipeline A** (deterministic extraction + reconciliation), NOT retrieval — so they are excluded here by design. This RAG eval covers the narrative 'why' questions.

- Metrics are LLM-judge approximations of RAGAS faithfulness / context precision / context recall (claim-counting + per-chunk relevance + rank-aware precision).
