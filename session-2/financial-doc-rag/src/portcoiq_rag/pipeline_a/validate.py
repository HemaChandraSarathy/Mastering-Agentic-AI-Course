"""Deterministic error-checks. Validation rule shapes (range, comparison)
and adds formula/reconciliation rules — the income-statement identities that MUST hold,
so a mis-keyed or mis-OCR'd number gets caught before it reaches the one-pager.

Rules run per period over a {metric_type: value} map.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from .models import ExtractedMetric, ValidationFlag

PeriodValues = dict[str, float]


@dataclass
class RangeRule:
    metric_type: str
    min: float | None = None
    max: float | None = None
    severity: str = "warning"

    def check(self, period: str, vals: PeriodValues) -> list[ValidationFlag]:
        if self.metric_type not in vals:
            return []
        v = vals[self.metric_type]
        flags = []
        if self.min is not None and v < self.min:
            flags.append(ValidationFlag(rule=f"range:{self.metric_type}", severity=self.severity,
                                        message=f"{self.metric_type}={v:g} below min {self.min:g}",
                                        metric_type=self.metric_type, period=period))
        if self.max is not None and v > self.max:
            flags.append(ValidationFlag(rule=f"range:{self.metric_type}", severity=self.severity,
                                        message=f"{self.metric_type}={v:g} above max {self.max:g}",
                                        metric_type=self.metric_type, period=period))
        return flags


@dataclass
class ComparisonRule:
    left: str
    op: str            # 'lte','lt','gte','gt'
    right: str
    severity: str = "warning"

    _OPS: dict[str, Callable[[float, float], bool]] = None  # type: ignore

    def check(self, period: str, vals: PeriodValues) -> list[ValidationFlag]:
        ops = {"lte": lambda a, b: a <= b, "lt": lambda a, b: a < b,
               "gte": lambda a, b: a >= b, "gt": lambda a, b: a > b}
        if self.left not in vals or self.right not in vals:
            return []
        a, b = vals[self.left], vals[self.right]
        if not ops[self.op](a, b):
            return [ValidationFlag(rule=f"cmp:{self.left}_{self.op}_{self.right}", severity=self.severity,
                                   message=f"expected {self.left}({a:g}) {self.op} {self.right}({b:g})",
                                   metric_type=self.left, period=period)]
        return []


@dataclass
class FormulaRule:
    """Reconciliation identity: target ≈ fn(values), within absolute tolerance ($M)."""
    name: str
    target: str
    fn: Callable[[PeriodValues], float | None]
    tolerance: float = 1.0
    severity: str = "error"

    def check(self, period: str, vals: PeriodValues) -> list[ValidationFlag]:
        if self.target not in vals:
            return []
        expected = self.fn(vals)
        if expected is None:
            return []
        actual = vals[self.target]
        if abs(actual - expected) > self.tolerance:
            return [ValidationFlag(rule=f"formula:{self.name}", severity=self.severity,
                                   message=f"{self.target}={actual:g} != {expected:g} "
                                           f"(Δ{actual - expected:+g}, tol {self.tolerance:g})",
                                   metric_type=self.target, period=period)]
        return []


def _safe(vals: PeriodValues, *keys: str):
    return [vals[k] for k in keys] if all(k in vals for k in keys) else None


# System default rules — pass on clean data, catch mis-keys / mis-OCR.
DEFAULT_RULES = [
    RangeRule("revenue", min=0),
    RangeRule("total_revenues", min=0),
    RangeRule("total_costs_and_expenses", min=0),
    RangeRule("income_tax_expense", min=0),
    RangeRule("gross_margin", min=0, max=100),
    ComparisonRule("net_income", "lte", "income_before_income_taxes"),
    ComparisonRule("income_tax_expense", "lte", "income_before_income_taxes"),
    ComparisonRule("total_costs_and_expenses", "lte", "total_revenues"),
    FormulaRule(
        "pretax = total_rev - total_costs",
        target="income_before_income_taxes",
        fn=lambda v: (v["total_revenues"] - v["total_costs_and_expenses"])
        if _safe(v, "total_revenues", "total_costs_and_expenses") else None,
    ),
    FormulaRule(
        "net = pretax - tax",
        target="net_income",
        fn=lambda v: (v["income_before_income_taxes"] - v["income_tax_expense"])
        if _safe(v, "income_before_income_taxes", "income_tax_expense") else None,
    ),
]


def validate(metrics: list[ExtractedMetric], rules=DEFAULT_RULES) -> list[ValidationFlag]:
    """Group mapped metrics by period, run every rule, collect flags."""
    by_period: dict[str, PeriodValues] = defaultdict(dict)
    for m in metrics:
        if m.metric_type is not None:
            by_period[m.period].setdefault(m.metric_type, m.value)

    flags: list[ValidationFlag] = []
    for period, vals in by_period.items():
        for rule in rules:
            flags.extend(rule.check(period, vals))
    return flags
