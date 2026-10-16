"""Provider-independent tools for fundamentals and regulatory filings.

These tools coordinate financial-data adapters and normalize their outputs for
the financial agent.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from src.data_sources.base import Statement

INCOME_ROWS = (
    "Total Revenue",
    "Operating Income",
    "Net Income",
    "EBITDA",
    "Diluted EPS",
)

CASH_FLOW_ROWS = (
    "Operating Cash Flow",
    "Free Cash Flow",
    "Capital Expenditure",
)

BALANCE_SHEET_ROWS = (
    "Cash Cash Equivalents And Short Term Investments",
    "Cash And Cash Equivalents",
    "Total Debt",
    "Stockholders Equity",
    "Total Assets",
    "Total Liabilities Net Minority Interest",
    "Current Assets",
    "Current Liabilities",
)


class FinancialDataClient(Protocol):
    """Data-source operations required by the financial tools."""

    def get_income_statement(self, symbol: str) -> Statement:
        """Return a normalized income statement."""

    def get_cash_flow_statement(self, symbol: str) -> Statement:
        """Return a normalized cash-flow statement."""

    def get_balance_sheet(self, symbol: str) -> Statement:
        """Return a normalized balance sheet."""


class SecDataClient(Protocol):
    """SEC data-source operation required by the filings tool."""

    def get_company_data(self, symbol: str) -> dict[str, Any]:
        """Return official facts and recent filings for a company."""


def _select_rows(
    statement: Mapping[str, Mapping[str, float | None]],
    wanted_rows: tuple[str, ...],
    *,
    empty_message: str,
) -> Statement | dict[str, str]:
    if not statement:
        return {"error": empty_message}

    selected: Statement = {}
    for row in wanted_rows:
        values = statement.get(row)
        if values is None:
            continue
        selected[row] = dict(list(values.items())[:4])

    return selected or {"error": empty_message}


def get_financials(
    client: FinancialDataClient,
    symbol: str,
) -> Statement | dict[str, str]:
    """Return up to four periods of selected income-statement rows."""

    return _select_rows(
        client.get_income_statement(symbol),
        INCOME_ROWS,
        empty_message="No financial statements found",
    )


def get_cash_flow(
    client: FinancialDataClient,
    symbol: str,
) -> Statement | dict[str, str]:
    """Return up to four periods of selected cash-flow rows."""

    return _select_rows(
        client.get_cash_flow_statement(symbol),
        CASH_FLOW_ROWS,
        empty_message="No cash-flow data found",
    )


def get_balance_sheet(
    client: FinancialDataClient,
    symbol: str,
) -> dict[str, Any]:
    """Return selected balance-sheet rows plus deterministic cash/debt metrics."""

    selected = _select_rows(
        client.get_balance_sheet(symbol),
        BALANCE_SHEET_ROWS,
        empty_message="No balance-sheet data found",
    )
    if "error" in selected:
        return selected

    cash = _latest_row_value(
        selected,
        "Cash Cash Equivalents And Short Term Investments",
        "Cash And Cash Equivalents",
    )
    debt = _latest_row_value(selected, "Total Debt")
    latest = {
        "cash": cash,
        "debt": debt,
        "net_debt": debt - cash if debt is not None and cash is not None else None,
        "cash_to_debt_ratio": (
            round(cash / debt, 4) if cash is not None and debt not in (None, 0) else None
        ),
        "total_assets": _latest_row_value(selected, "Total Assets"),
        "total_liabilities": _latest_row_value(
            selected,
            "Total Liabilities Net Minority Interest",
        ),
        "stockholders_equity": _latest_row_value(selected, "Stockholders Equity"),
    }
    return {"statement": selected, "latest": latest}


def get_financial_growth(
    client: FinancialDataClient,
    symbol: str,
) -> dict[str, Any]:
    """Calculate deterministic latest-period revenue and earnings growth."""

    statement = client.get_income_statement(symbol)
    if not statement:
        return {"error": "No financial statements found"}

    rows = {
        "revenue_growth_percent": statement.get("Total Revenue"),
        "net_income_growth_percent": statement.get("Net Income"),
        "diluted_eps_growth_percent": statement.get("Diluted EPS"),
    }
    result: dict[str, Any] = {}
    periods: list[str] = []
    for metric, values in rows.items():
        if not values:
            result[metric] = None
            continue
        items = list(values.items())
        if len(items) < 2:
            result[metric] = None
            continue
        if not periods:
            periods = [str(items[0][0]), str(items[1][0])]
        latest, prior = items[0][1], items[1][1]
        result[metric] = _growth_percent(latest, prior)

    result["latest_period"] = periods[0] if periods else None
    result["prior_period"] = periods[1] if len(periods) > 1 else None
    return result


def _latest_row_value(statement: Mapping[str, Any], *rows: str) -> float | None:
    for row in rows:
        values = statement.get(row)
        if isinstance(values, Mapping):
            for value in values.values():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return float(value)
    return None


def _growth_percent(latest: object, prior: object) -> float | None:
    if (
        not isinstance(latest, (int, float))
        or isinstance(latest, bool)
        or not isinstance(prior, (int, float))
        or isinstance(prior, bool)
        or prior == 0
    ):
        return None
    return round((float(latest) / float(prior) - 1) * 100, 2)


def get_sec_edgar(
    client: SecDataClient,
    symbol: str,
) -> dict[str, Any]:
    """Return normalized official company facts and recent SEC filings."""

    return client.get_company_data(symbol)
