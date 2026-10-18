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
    "Operating Expenses",
    "Operating Income",
    "Net Income",
    "EBITDA",
    "Diluted EPS",
)

OPERATING_EXPENSE_ROWS = (
    "Operating Expenses",
    "Total Operating Expenses",
    "Operating Expense",
    "Total Operating Expense",
)

GROSS_PROFIT_ROWS = ("Gross Profit",)
OPERATING_INCOME_ROWS = ("Operating Income", "Operating Income Loss")

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
    max_periods: int = 4,
) -> Statement | dict[str, str]:
    if not statement:
        return {"error": empty_message}

    selected: Statement = {}
    for row in wanted_rows:
        values = statement.get(row)
        if values is None:
            continue
        selected[row] = dict(list(values.items())[:max_periods])

    return selected or {"error": empty_message}


def get_financials(
    client: FinancialDataClient,
    symbol: str,
) -> Statement | dict[str, str]:
    """Return up to five periods of selected income-statement rows.

    Operating expenses use a directly reported operating-expense row when
    available. Missing periods are derived as gross profit minus operating
    income, which avoids treating total costs and expenses as equivalent to
    operating expenses.
    """

    statement = client.get_income_statement(symbol)
    selected = _select_rows(
        statement,
        INCOME_ROWS,
        empty_message="No financial statements found",
        max_periods=5,
    )
    if "error" in selected:
        return selected

    operating_expenses = derive_operating_expenses(statement)
    if operating_expenses:
        selected["Operating Expenses"] = dict(
            list(operating_expenses.items())[:5]
        )
    return {row: selected[row] for row in INCOME_ROWS if row in selected}


def derive_operating_expenses(
    statement: Mapping[str, Mapping[str, float | None]],
) -> dict[str, float]:
    """Return reported or deterministically derived operating expenses.

    The direct provider row takes precedence for each period. Where it is
    unavailable, ``Gross Profit - Operating Income`` supplies the value because
    gross profit already excludes cost of revenue. Generic total-cost rows are
    intentionally excluded because they are not semantically equivalent.
    """

    if not statement:
        return {}
    direct = _first_statement_row(statement, OPERATING_EXPENSE_ROWS)
    gross_profit = _first_statement_row(statement, GROSS_PROFIT_ROWS)
    operating_income = _first_statement_row(statement, OPERATING_INCOME_ROWS)
    periods = dict.fromkeys(
        [*direct.keys(), *gross_profit.keys(), *operating_income.keys()]
    )
    expenses: dict[str, float] = {}
    for period in periods:
        direct_value = _number(direct.get(period))
        if direct_value is not None:
            expenses[str(period)] = direct_value
            continue
        gross_profit_value = _number(gross_profit.get(period))
        operating_income_value = _number(operating_income.get(period))
        if gross_profit_value is not None and operating_income_value is not None:
            expenses[str(period)] = gross_profit_value - operating_income_value
    return expenses


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
    trend_rows = {
        "cash_growth_percent": (
            "Cash Cash Equivalents And Short Term Investments",
            "Cash And Cash Equivalents",
        ),
        "debt_growth_percent": ("Total Debt",),
        "assets_growth_percent": ("Total Assets",),
        "liabilities_growth_percent": (
            "Total Liabilities Net Minority Interest",
        ),
        "equity_growth_percent": ("Stockholders Equity",),
    }
    trends: dict[str, Any] = {}
    latest_period: str | None = None
    prior_period: str | None = None
    for metric, rows in trend_rows.items():
        periods, values = _latest_two_row_values(selected, *rows)
        trends[metric] = (
            _growth_percent(values[0], values[1]) if len(values) == 2 else None
        )
        if latest_period is None and len(periods) == 2:
            latest_period, prior_period = periods
    trends["latest_period"] = latest_period
    trends["prior_period"] = prior_period
    return {"statement": selected, "latest": latest, "trends": trends}


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


def _first_statement_row(
    statement: Mapping[str, Mapping[str, float | None]],
    names: tuple[str, ...],
) -> Mapping[str, float | None]:
    """Return the first case-insensitive statement row matching ``names``."""

    normalized_rows = {
        str(row).strip().casefold(): values for row, values in statement.items()
    }
    for name in names:
        values = normalized_rows.get(name.casefold())
        if isinstance(values, Mapping):
            return values
    return {}


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _latest_two_row_values(
    statement: Mapping[str, Any],
    *rows: str,
) -> tuple[list[str], list[float]]:
    for row in rows:
        raw_values = statement.get(row)
        if not isinstance(raw_values, Mapping):
            continue
        periods: list[str] = []
        values: list[float] = []
        for period, value in raw_values.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                periods.append(str(period))
                values.append(float(value))
            if len(values) == 2:
                return periods, values
    return [], []


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
