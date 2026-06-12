"""Canonical PE metric taxonomy + deterministic label→metric mapping.

A canonical PE metric taxonomy
(38 metrics across 6 categories) so Pipeline A maps into the SAME canonical set the
product uses — this is the "auto-mapping into the template / zero reshaping" promise.

Difference from an LLM extractor: that approach extracts with Claude from free text. Pipeline A is
DETERMINISTIC (table parse → label match), so the LLM extraction step is replaced by
`map_label()`, a normalized lookup over `LABEL_ALIASES`. Anything that doesn't map is
returned as `None` (unmapped) and surfaced to the analyst at the confirm gate rather
than force-fit — consistent with the metrics-integrity rule (never invent a mapping).

Note on ConocoPhillips (the placeholder corpus): COP is an oil & gas E&P issuer, so many
of the 38 metrics are SaaS-specific (arr, nrr, churn) and simply won't appear. COP filings
map cleanly to revenue / cash / headcount / working_capital, etc.; figures like EBITDA are
often not reported directly in E&P statements — those stay unmapped rather than being
derived and presented as if reported.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class MetricCategory(str, Enum):
    FINANCIALS = "financials"
    BUDGET_VS_ACTUAL = "budget_vs_actual"
    DEBT_AND_LIQUIDITY = "debt_and_liquidity"
    REVENUE_QUALITY = "revenue_quality"
    COMMERCIAL = "commercial"
    OPERATIONS = "operations"
    # Extension beyond the canonical 38 — see EXTENSION_METRICS below.
    INCOME_STATEMENT = "income_statement"


class Unit(str, Enum):
    USD_M = "$M"        # millions USD
    PCT = "%"
    MULTIPLE = "x"      # e.g. leverage 4.2x
    COUNT = "#"
    TEXT = "text"
    POINTS = "pts"      # NPS


@dataclass(frozen=True)
class MetricDef:
    metric_type: str
    category: MetricCategory
    label: str
    unit: Unit
    description: str


# --- The 38 canonical metrics (verbatim port) -------------------------------
CANONICAL_METRICS: dict[str, MetricDef] = {
    m.metric_type: m
    for m in [
        # FINANCIALS
        MetricDef("revenue", MetricCategory.FINANCIALS, "Revenue", Unit.USD_M, "Total revenue / net sales"),
        MetricDef("ebitda", MetricCategory.FINANCIALS, "EBITDA", Unit.USD_M, "EBITDA"),
        MetricDef("gross_margin", MetricCategory.FINANCIALS, "Gross margin", Unit.PCT, "Gross margin"),
        MetricDef("revenue_growth_yoy", MetricCategory.FINANCIALS, "Revenue growth YoY", Unit.PCT, "Revenue growth year over year"),
        MetricDef("ltm_ebitda", MetricCategory.FINANCIALS, "LTM EBITDA", Unit.USD_M, "Last-twelve-months EBITDA"),
        MetricDef("ltm_cash_taxes", MetricCategory.FINANCIALS, "LTM cash taxes", Unit.USD_M, "LTM cash taxes paid"),
        # BUDGET_VS_ACTUAL
        MetricDef("revenue_vs_budget", MetricCategory.BUDGET_VS_ACTUAL, "Revenue vs budget", Unit.PCT, "Revenue vs budget variance (positive = above)"),
        MetricDef("ebitda_vs_budget", MetricCategory.BUDGET_VS_ACTUAL, "EBITDA vs budget", Unit.PCT, "EBITDA vs budget variance (positive = above)"),
        MetricDef("fcf_vs_budget", MetricCategory.BUDGET_VS_ACTUAL, "FCF vs budget", Unit.PCT, "Free cash flow vs budget variance"),
        MetricDef("budget_revenue", MetricCategory.BUDGET_VS_ACTUAL, "Budget revenue", Unit.USD_M, "Full-year budget revenue"),
        MetricDef("budget_ebitda", MetricCategory.BUDGET_VS_ACTUAL, "Budget EBITDA", Unit.USD_M, "Full-year budget EBITDA"),
        MetricDef("forecast_revenue", MetricCategory.BUDGET_VS_ACTUAL, "Forecast revenue", Unit.USD_M, "Updated full-year forecast revenue"),
        MetricDef("forecast_ebitda", MetricCategory.BUDGET_VS_ACTUAL, "Forecast EBITDA", Unit.USD_M, "Updated full-year forecast EBITDA"),
        # DEBT_AND_LIQUIDITY
        MetricDef("net_debt", MetricCategory.DEBT_AND_LIQUIDITY, "Net debt", Unit.USD_M, "Gross debt minus cash"),
        MetricDef("cash", MetricCategory.DEBT_AND_LIQUIDITY, "Cash", Unit.USD_M, "Cash and cash equivalents"),
        MetricDef("leverage_ratio", MetricCategory.DEBT_AND_LIQUIDITY, "Leverage", Unit.MULTIPLE, "Net debt / EBITDA"),
        MetricDef("covenant_level", MetricCategory.DEBT_AND_LIQUIDITY, "Covenant level", Unit.MULTIPLE, "Financial covenant threshold (the limit)"),
        MetricDef("covenant_headroom", MetricCategory.DEBT_AND_LIQUIDITY, "Covenant headroom", Unit.USD_M, "Headroom above covenant ($M or %)"),
        MetricDef("available_liquidity", MetricCategory.DEBT_AND_LIQUIDITY, "Available liquidity", Unit.USD_M, "Total available liquidity"),
        MetricDef("rcf_capacity", MetricCategory.DEBT_AND_LIQUIDITY, "RCF capacity", Unit.USD_M, "Revolving credit facility capacity"),
        MetricDef("next_debt_maturity", MetricCategory.DEBT_AND_LIQUIDITY, "Next debt maturity", Unit.TEXT, "Next debt maturity date"),
        MetricDef("weighted_avg_interest_rate", MetricCategory.DEBT_AND_LIQUIDITY, "Wtd avg interest rate", Unit.PCT, "Weighted average interest rate"),
        # REVENUE_QUALITY
        MetricDef("arr", MetricCategory.REVENUE_QUALITY, "ARR", Unit.USD_M, "Annual recurring revenue (SaaS)"),
        MetricDef("recurring_revenue_pct", MetricCategory.REVENUE_QUALITY, "Recurring revenue %", Unit.PCT, "Recurring revenue as % of total"),
        MetricDef("nrr", MetricCategory.REVENUE_QUALITY, "NRR", Unit.PCT, "Net revenue retention (SaaS)"),
        MetricDef("gross_retention_rate", MetricCategory.REVENUE_QUALITY, "Gross retention", Unit.PCT, "Gross / logo retention"),
        MetricDef("customer_churn", MetricCategory.REVENUE_QUALITY, "Customer churn", Unit.PCT, "Customer / logo churn rate"),
        MetricDef("top10_customer_concentration", MetricCategory.REVENUE_QUALITY, "Top-10 concentration", Unit.PCT, "Revenue from top 10 customers as % of total"),
        MetricDef("active_customers", MetricCategory.REVENUE_QUALITY, "Active customers", Unit.COUNT, "Active customer count"),
        MetricDef("contracted_backlog", MetricCategory.REVENUE_QUALITY, "Contracted backlog", Unit.USD_M, "Contracted revenue backlog"),
        MetricDef("nps", MetricCategory.REVENUE_QUALITY, "NPS", Unit.POINTS, "Net Promoter Score"),
        # COMMERCIAL
        MetricDef("sales_pipeline_value", MetricCategory.COMMERCIAL, "Sales pipeline", Unit.USD_M, "Total sales pipeline / pipeline value"),
        MetricDef("win_rate", MetricCategory.COMMERCIAL, "Win rate", Unit.PCT, "Sales win rate"),
        MetricDef("vcp_ebitda_impact", MetricCategory.COMMERCIAL, "VCP EBITDA impact", Unit.USD_M, "Value creation plan EBITDA impact"),
        # OPERATIONS
        MetricDef("headcount", MetricCategory.OPERATIONS, "Headcount", Unit.COUNT, "Total headcount / FTE count"),
        MetricDef("working_capital", MetricCategory.OPERATIONS, "Working capital", Unit.USD_M, "Net working capital"),
        MetricDef("dso", MetricCategory.OPERATIONS, "DSO", Unit.COUNT, "Days sales outstanding"),
        MetricDef("net_debt_at_entry", MetricCategory.OPERATIONS, "Net debt at entry", Unit.USD_M, "Net debt at acquisition/entry (IC memos only)"),
    ]
}

assert len(CANONICAL_METRICS) == 38, f"expected 38 canonical metrics, got {len(CANONICAL_METRICS)}"

# --- Income-statement extension (NOT part of the canonical 38) ----------------
# The 38 are PE-portco-flavored (EBITDA, leverage, NRR). A public E&P issuer like
# ConocoPhillips reports net income / EPS, not EBITDA, so a strict 38-metric map is
# nearly empty. These extension metrics are universally-reported GAAP income-statement
# lines — real, unambiguous, and what COP actually files. Kept separate and clearly
# labeled so the canonical 38 stay intact; integrity rule = never relabel net income as
# EBITDA to force a match.
EXTENSION_METRICS: dict[str, MetricDef] = {
    m.metric_type: m
    for m in [
        MetricDef("total_revenues", MetricCategory.INCOME_STATEMENT, "Total revenues & other income", Unit.USD_M, "Top-line total revenues and other income"),
        MetricDef("total_costs_and_expenses", MetricCategory.INCOME_STATEMENT, "Total costs & expenses", Unit.USD_M, "Total costs and expenses"),
        MetricDef("income_before_income_taxes", MetricCategory.INCOME_STATEMENT, "Income before income taxes", Unit.USD_M, "Pre-tax income"),
        MetricDef("income_tax_expense", MetricCategory.INCOME_STATEMENT, "Income tax provision", Unit.USD_M, "Income tax provision (benefit)"),
        MetricDef("net_income", MetricCategory.INCOME_STATEMENT, "Net income", Unit.USD_M, "Net income (loss)"),
        MetricDef("eps_diluted", MetricCategory.INCOME_STATEMENT, "Diluted EPS", Unit.TEXT, "Net income per diluted share ($/sh)"),
    ]
}

# Single lookup used by map_label/validate: canonical 38 + extension.
ALL_METRICS: dict[str, MetricDef] = {**CANONICAL_METRICS, **EXTENSION_METRICS}

# --- Suppression lists (ported) ---------------------------------------------
SAAS_ONLY_METRICS = {"arr", "nrr", "gross_retention_rate"}
IC_MEMO_SUPPRESSED = {
    "budget_revenue", "budget_ebitda", "forecast_revenue", "forecast_ebitda",
    "revenue_vs_budget", "ebitda_vs_budget", "fcf_vs_budget", "vcp_ebitda_impact",
    "covenant_headroom",
}
NON_IC_SUPPRESSED = {"net_debt_at_entry"}

# --- Deterministic label aliases --------------------------------------------
# Lowercased, punctuation-stripped raw labels → canonical metric_type.
# Conservative on purpose: only map labels that unambiguously equal the canonical
# metric. Ambiguous items (e.g. "net income", "operating income") are intentionally
# left OUT so they surface as unmapped rather than being misclassified as EBITDA.
LABEL_ALIASES: dict[str, str] = {
    # revenue
    "revenue": "revenue",
    "revenues": "revenue",
    "total revenue": "revenue",
    "total revenues": "revenue",
    "net sales": "revenue",
    "net revenue": "revenue",
    "net revenues": "revenue",
    "sales and other operating revenues": "revenue",
    "sales and other operating revenue": "revenue",
    # income-statement extension (real GAAP lines COP reports)
    "total revenues and other income": "total_revenues",
    "total revenue and other income": "total_revenues",
    "total costs and expenses": "total_costs_and_expenses",
    "income before income taxes": "income_before_income_taxes",
    "income before income tax": "income_before_income_taxes",
    "income tax provision": "income_tax_expense",
    "provision for income taxes": "income_tax_expense",
    "net income": "net_income",
    "net income loss": "net_income",
    "diluted eps": "eps_diluted",
    "eps diluted": "eps_diluted",
    "diluted earnings per share": "eps_diluted",
    "net income per share of common stock diluted": "eps_diluted",
    # ebitda
    "ebitda": "ebitda",
    "adjusted ebitda": "ebitda",
    "ltm ebitda": "ltm_ebitda",
    # margins / growth
    "gross margin": "gross_margin",
    "gross profit margin": "gross_margin",
    "revenue growth": "revenue_growth_yoy",
    "revenue growth yoy": "revenue_growth_yoy",
    "yoy revenue growth": "revenue_growth_yoy",
    # cash & debt
    "cash": "cash",
    "cash and cash equivalents": "cash",
    "cash & cash equivalents": "cash",
    "cash and equivalents": "cash",
    "net debt": "net_debt",
    "leverage": "leverage_ratio",
    "net leverage": "leverage_ratio",
    "leverage ratio": "leverage_ratio",
    "net debt / ebitda": "leverage_ratio",
    "available liquidity": "available_liquidity",
    "total liquidity": "available_liquidity",
    "revolving credit facility": "rcf_capacity",
    "rcf": "rcf_capacity",
    "weighted average interest rate": "weighted_avg_interest_rate",
    "next debt maturity": "next_debt_maturity",
    # revenue quality
    "arr": "arr",
    "annual recurring revenue": "arr",
    "recurring revenue": "recurring_revenue_pct",
    "nrr": "nrr",
    "net revenue retention": "nrr",
    "gross retention": "gross_retention_rate",
    "logo retention": "gross_retention_rate",
    "customer churn": "customer_churn",
    "logo churn": "customer_churn",
    "churn": "customer_churn",
    "top 10 customer concentration": "top10_customer_concentration",
    "top-10 customer concentration": "top10_customer_concentration",
    "active customers": "active_customers",
    "contracted backlog": "contracted_backlog",
    "backlog": "contracted_backlog",
    "nps": "nps",
    "net promoter score": "nps",
    # commercial
    "sales pipeline": "sales_pipeline_value",
    "pipeline value": "sales_pipeline_value",
    "win rate": "win_rate",
    # operations
    "headcount": "headcount",
    "employees": "headcount",
    "total employees": "headcount",
    "fte": "headcount",
    "ftes": "headcount",
    "full-time employees": "headcount",
    "working capital": "working_capital",
    "net working capital": "working_capital",
    "dso": "dso",
    "days sales outstanding": "dso",
}


def normalize_label(raw: str) -> str:
    """Lowercase, collapse whitespace, strip trailing footnote markers / punctuation."""
    s = raw.strip().lower()
    s = re.sub(r"[\(\[].*?[\)\]]", "", s)        # drop parentheticals e.g. "($M)", "(1)"
    s = re.sub(r"[^a-z0-9/&\s\-]", " ", s)        # keep alnum, slash, ampersand, hyphen
    s = re.sub(r"\s+", " ", s).strip()
    return s


def map_label(raw: str) -> str | None:
    """Map a raw financial-statement row label to a canonical metric_type, or None.

    None means 'unmapped' — surface to the analyst at the confirm gate; never force-fit.
    """
    norm = normalize_label(raw)
    if norm in LABEL_ALIASES:
        return LABEL_ALIASES[norm]
    # exact metric name match (e.g. already snake_case)
    snake = norm.replace(" ", "_").replace("-", "_")
    if snake in ALL_METRICS:
        return snake
    return None


def is_applicable(metric_type: str, *, doc_type: str | None = None, industry: str | None = None) -> bool:
    """Apply the standard suppression rules (IC-memo / non-IC / SaaS-only)."""
    is_ic = doc_type == "ic_memo"
    if is_ic and metric_type in IC_MEMO_SUPPRESSED:
        return False
    if not is_ic and metric_type in NON_IC_SUPPRESSED:
        return False
    if industry == "industrial" and metric_type in SAAS_ONLY_METRICS:
        return False
    return True
