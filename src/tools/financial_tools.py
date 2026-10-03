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


class FinancialDataClient(Protocol):
    """Data-source operations required by the financial tools."""

    def get_income_statement(self, symbol: str) -> Statement:
        """Return a normalized income statement."""

    def get_cash_flow_statement(self, symbol: str) -> Statement:
        """Return a normalized cash-flow statement."""


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


def get_sec_edgar(
    client: SecDataClient,
    symbol: str,
) -> dict[str, Any]:
    """Return normalized official company facts and recent SEC filings."""

    return client.get_company_data(symbol)
