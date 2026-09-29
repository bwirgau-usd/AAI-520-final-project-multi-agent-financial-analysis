"""Deterministic analysis of company financial statements and valuation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Number
from typing import Any, Protocol

from src.data_sources.base import Statement
from src.data_sources.yahoo_finance import YahooFinanceClient

REVENUE_ROWS = ("Total Revenue", "Operating Revenue", "Revenue")
NET_INCOME_ROWS = (
    "Net Income",
    "Net Income Common Stockholders",
    "Net Income Continuous Operations",
)
EPS_ROWS = ("Diluted EPS", "Basic EPS")
GROSS_PROFIT_ROWS = ("Gross Profit",)
OPERATING_INCOME_ROWS = ("Operating Income",)
CASH_ROWS = (
    "Cash Cash Equivalents And Short Term Investments",
    "Cash And Cash Equivalents",
    "Cash Financial",
)
DEBT_ROWS = ("Total Debt",)
ASSET_ROWS = ("Total Assets",)
LIABILITY_ROWS = (
    "Total Liabilities Net Minority Interest",
    "Total Liabilities",
)
EQUITY_ROWS = (
    "Stockholders Equity",
    "Total Equity Gross Minority Interest",
    "Common Stock Equity",
)
TRAILING_PE_ROWS = ("Trailing P/E", "Trailing PE", "trailingPE")
FORWARD_PE_ROWS = ("Forward P/E", "Forward PE", "forwardPE")


class FinancialAnalysisClient(Protocol):
    """Provider operations required by ``FinancialAgent``."""

    def get_income_statement(self, symbol: str) -> Statement:
        """Return a normalized income statement."""

    def get_balance_sheet(self, symbol: str) -> Statement:
        """Return a normalized balance sheet."""

    def get_valuation(self, symbol: str) -> Statement:
        """Return normalized valuation measures."""


class FinancialAgent:
    """Collect Yahoo financial data and calculate explainable company metrics."""

    def __init__(self, client: FinancialAnalysisClient | None = None) -> None:
        self._client = client if client is not None else YahooFinanceClient()

    def analyze(self, symbol: str) -> dict[str, Any]:
        """Return structured financial analysis for one stock symbol.

        Earnings growth is period-over-period net-income growth. Financial
        statement dictionaries are expected in newest-first order, matching
        the normalized Yahoo Finance adapter output.
        """

        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must be a non-empty string")

        income_statement = self._client.get_income_statement(normalized_symbol)
        balance_sheet = self._client.get_balance_sheet(normalized_symbol)
        valuation = self._client.get_valuation(normalized_symbol)

        revenue = _metric(income_statement, REVENUE_ROWS)
        net_income = _metric(income_statement, NET_INCOME_ROWS)
        eps = _metric(income_statement, EPS_ROWS)
        cash = _metric(balance_sheet, CASH_ROWS)
        debt = _metric(balance_sheet, DEBT_ROWS)
        assets = _metric(balance_sheet, ASSET_ROWS)
        liabilities = _metric(balance_sheet, LIABILITY_ROWS)
        equity = _metric(balance_sheet, EQUITY_ROWS)

        margins = {
            "gross_margin": _margin_metric(
                income_statement,
                GROSS_PROFIT_ROWS,
                REVENUE_ROWS,
            ),
            "operating_margin": _margin_metric(
                income_statement,
                OPERATING_INCOME_ROWS,
                REVENUE_ROWS,
            ),
            "net_margin": _margin_metric(
                income_statement,
                NET_INCOME_ROWS,
                REVENUE_ROWS,
            ),
        }
        pe = {
            "trailing": _current_value(valuation, TRAILING_PE_ROWS),
            "forward": _current_value(valuation, FORWARD_PE_ROWS),
        }
        balance_sheet_trends = {
            "cash": _trend_summary(cash),
            "debt": _trend_summary(debt),
            "assets": _trend_summary(assets),
            "liabilities": _trend_summary(liabilities),
            "equity": _trend_summary(equity),
            "debt_to_equity": _ratio(debt["value"], equity["value"]),
        }

        analysis: dict[str, Any] = {
            "symbol": normalized_symbol,
            "revenue": revenue,
            "revenue_growth_percent": revenue["growth_percent"],
            "net_income": net_income,
            "earnings_growth_percent": net_income["growth_percent"],
            "eps": eps,
            "margins": margins,
            "pe": pe,
            "cash": cash,
            "debt": debt,
            "balance_sheet_trends": balance_sheet_trends,
        }
        analysis["data_gaps"] = _data_gaps(analysis)
        analysis["findings"] = _findings(analysis)
        return analysis


def _series(statement: Statement, row_names: tuple[str, ...]) -> Mapping[str, Any]:
    for row_name in row_names:
        values = statement.get(row_name)
        if isinstance(values, Mapping):
            return values
    return {}


def _metric(statement: Statement, row_names: tuple[str, ...]) -> dict[str, Any]:
    points = [
        (str(period), number)
        for period, value in _series(statement, row_names).items()
        if (number := _number(value)) is not None
    ]
    latest = points[0] if points else (None, None)
    previous = points[1] if len(points) > 1 else (None, None)
    return {
        "period": latest[0],
        "value": latest[1],
        "previous_period": previous[0],
        "previous_value": previous[1],
        "growth_percent": _growth_percent(latest[1], previous[1]),
        "trend": _trend(latest[1], previous[1]),
    }


def _margin_metric(
    statement: Statement,
    numerator_rows: tuple[str, ...],
    revenue_rows: tuple[str, ...],
) -> dict[str, Any]:
    numerator = _series(statement, numerator_rows)
    revenue = _series(statement, revenue_rows)
    points: list[tuple[str, float]] = []
    for period, revenue_value in revenue.items():
        denominator = _number(revenue_value)
        value = _number(numerator.get(period))
        if denominator in (None, 0) or value is None:
            continue
        points.append((str(period), value / denominator * 100))

    latest = points[0] if points else (None, None)
    previous = points[1] if len(points) > 1 else (None, None)
    change = (
        None
        if latest[1] is None or previous[1] is None
        else round(latest[1] - previous[1], 2)
    )
    return {
        "period": latest[0],
        "value_percent": _round(latest[1]),
        "previous_period": previous[0],
        "previous_value_percent": _round(previous[1]),
        "change_percentage_points": change,
        "trend": _trend(latest[1], previous[1]),
    }


def _current_value(statement: Statement, row_names: tuple[str, ...]) -> float | None:
    values = _series(statement, row_names)
    current = _number(values.get("Current"))
    if current is not None:
        return current
    return next(
        (number for value in values.values() if (number := _number(value)) is not None),
        None,
    )


def _trend_summary(metric: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "latest_period": metric["period"],
        "latest_value": metric["value"],
        "previous_period": metric["previous_period"],
        "previous_value": metric["previous_value"],
        "growth_percent": metric["growth_percent"],
        "direction": metric["trend"],
    }


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Number):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def _growth_percent(latest: object, previous: object) -> float | None:
    latest_number = _number(latest)
    previous_number = _number(previous)
    if latest_number is None or previous_number in (None, 0):
        return None
    return round((latest_number - previous_number) / abs(previous_number) * 100, 2)


def _trend(latest: object, previous: object) -> str:
    latest_number = _number(latest)
    previous_number = _number(previous)
    if latest_number is None or previous_number is None:
        return "unavailable"
    if math.isclose(latest_number, previous_number):
        return "stable"
    return "increasing" if latest_number > previous_number else "decreasing"


def _ratio(numerator: object, denominator: object) -> float | None:
    numerator_number = _number(numerator)
    denominator_number = _number(denominator)
    if numerator_number is None or denominator_number in (None, 0):
        return None
    return round(numerator_number / denominator_number, 2)


def _data_gaps(analysis: Mapping[str, Any]) -> list[str]:
    gaps: list[str] = []
    checks = {
        "revenue": analysis["revenue"]["value"],
        "revenue growth": analysis["revenue_growth_percent"],
        "net income": analysis["net_income"]["value"],
        "earnings growth": analysis["earnings_growth_percent"],
        "EPS": analysis["eps"]["value"],
        "gross margin": analysis["margins"]["gross_margin"]["value_percent"],
        "operating margin": analysis["margins"]["operating_margin"][
            "value_percent"
        ],
        "net margin": analysis["margins"]["net_margin"]["value_percent"],
        "trailing P/E": analysis["pe"]["trailing"],
        "cash": analysis["cash"]["value"],
        "debt": analysis["debt"]["value"],
        "total assets": analysis["balance_sheet_trends"]["assets"][
            "latest_value"
        ],
        "total liabilities": analysis["balance_sheet_trends"]["liabilities"][
            "latest_value"
        ],
        "shareholders' equity": analysis["balance_sheet_trends"]["equity"][
            "latest_value"
        ],
    }
    for label, value in checks.items():
        if value is None:
            gaps.append(f"No usable {label} data was returned.")
    return gaps


def _findings(analysis: Mapping[str, Any]) -> list[str]:
    findings: list[str] = []
    for label, metric_name in (("Revenue", "revenue"), ("Net income", "net_income")):
        metric = analysis[metric_name]
        growth = metric["growth_percent"]
        if growth is not None:
            findings.append(
                f"{label} changed {growth:+.2f}% from "
                f"{metric['previous_period']} to {metric['period']}."
            )

    for label, margin in analysis["margins"].items():
        change = margin["change_percentage_points"]
        if change is not None:
            readable_label = label.replace("_", " ").capitalize()
            findings.append(
                f"{readable_label} changed {change:+.2f} percentage points."
            )

    trailing_pe = analysis["pe"]["trailing"]
    forward_pe = analysis["pe"]["forward"]
    if trailing_pe is not None:
        message = f"Trailing P/E is {trailing_pe:.2f}x"
        if forward_pe is not None:
            message += f" and forward P/E is {forward_pe:.2f}x"
        findings.append(message + ".")

    for label in ("cash", "debt"):
        metric = analysis[label]
        if metric["trend"] != "unavailable":
            findings.append(
                f"{label.capitalize()} is {metric['trend']} versus "
                f"{metric['previous_period']}."
            )

    for label in ("assets", "liabilities", "equity"):
        trend = analysis["balance_sheet_trends"][label]
        if trend["direction"] != "unavailable":
            findings.append(
                f"Total {label} are {trend['direction']} versus "
                f"{trend['previous_period']}."
            )
    return findings
