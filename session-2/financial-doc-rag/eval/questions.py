"""Ground-truth evaluation set for the fictional Meridian sample (narrative RAG).

Each answerable question has a verified `reference` answer (we authored the data, so the
answers are exact) and `relevant` source-file substrings — enabling RAGAS-style context
precision / recall, not just hit@k. Unanswerable questions test the refusal path.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalQ:
    id: str
    question: str
    answerable: bool
    reference: str = ""                       # verified ground-truth answer
    relevant: list = field(default_factory=list)  # source-file substrings that contain the answer


QUESTIONS: list[EvalQ] = [
    EvalQ("M1", "What new contract did Meridian win in Q3 2025, and how large is it at full run-rate?",
          True,
          "A five-year supply agreement with a top-three commercial aerospace OEM for precision-machined "
          "titanium structural components, ramping to about $40 million of annual revenue by 2028.",
          ["Q3_2025_Earnings_Call", "Analyst_Report"]),
    EvalQ("M2", "When is the aerospace program expected to begin contributing to revenue?",
          True, "In the second quarter of 2026.", ["Q3_2025_Earnings_Call"]),
    EvalQ("M3", "What drove the gross margin expansion to 35.0% in Q3 2025?",
          True,
          "First-half pricing actions now fully in effect, plus easing input costs as specialty-alloy and "
          "steel prices normalized and freight came down.",
          ["Q3_2025_Earnings_Call"]),
    EvalQ("M4", "What was Meridian's net leverage in Q3 2025 and where did it start the year?",
          True, "Net leverage was 2.5x in Q3 2025, down from 2.8x at the start of the year.",
          ["Q3_2025_Earnings_Call", "Analyst_Report"]),
    EvalQ("M5", "Why did working capital rise in Q3 2025?",
          True, "It rose to $50 million because Meridian built titanium raw-material inventory ahead of "
          "the aerospace ramp.", ["Q3_2025_Earnings_Call"]),
    EvalQ("M6", "What is Meridian's capital allocation priority?",
          True, "Debt paydown until roughly 2.0x leverage, after which it will revisit bolt-on M&A; no "
          "dividend is contemplated.", ["Q3_2025_Earnings_Call"]),
    EvalQ("M7", "What did management say about free cash flow conversion during the ramp?",
          True, "About 50% of EBITDA through the first half of 2026, normalizing toward 70% in steady "
          "state.", ["Q3_2025_Earnings_Call"]),
    EvalQ("M8", "What capacity investment did Meridian make in Q3 2025?",
          True, "It commissioned a second machining cell at its Dayton, Ohio facility in September, adding "
          "about 15% titanium machining capacity.", ["Q3_2025_Earnings_Call", "Analyst_Report"]),
    EvalQ("M9", "What is the main risk to the 2026 aerospace ramp?",
          True, "OEM qualification / PPAP (first-article) timing; a one-quarter slip would push out the "
          "revenue contribution.", ["Q3_2025_Earnings_Call", "Analyst_Report"]),
    EvalQ("M10", "What full-year 2025 revenue guidance did Meridian give?",
          True, "It raised full-year 2025 revenue guidance to a range of $425 to $430 million.",
          ["Q3_2025_Earnings_Call"]),

    # --- unanswerable (must refuse) ---
    EvalQ("R1", "What was Meridian's revenue in 2019?", False),
    EvalQ("R2", "Who is Meridian's largest customer by name?", False),
    EvalQ("R3", "What is the CEO's annual compensation?", False),
]

ANSWERABLE = [q for q in QUESTIONS if q.answerable]
UNANSWERABLE = [q for q in QUESTIONS if not q.answerable]


if __name__ == "__main__":
    print(f"{len(QUESTIONS)} questions: {len(ANSWERABLE)} answerable, {len(UNANSWERABLE)} refusal")
