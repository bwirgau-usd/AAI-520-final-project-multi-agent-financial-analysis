"""Yahoo Finance ingestion adapter.

All provider-specific ``yfinance`` calls and response parsing belong in this
module. Yahoo Finance is the project's initial market and financial-data
source.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any

from src.data_sources.base import Statement


TickerFactory = Callable[[str], Any]


class YahooFinanceClient:
    """Read and normalize market data supplied by ``yfinance``."""

    def __init__(self, ticker_factory: TickerFactory | None = None) -> None:
        self._ticker_factory = ticker_factory

    def get_history(self, symbol: str, period: str = "1y") -> list[float]:
        """Return non-null closing prices for the requested period."""

        history = self._ticker(symbol).history(period=period)
        if history is None or getattr(history, "empty", False):
            return []
        if "Close" not in history:
            return []

        close = history["Close"].dropna()
        return [float(value) for value in close]

    def get_company_info(self, symbol: str) -> dict[str, Any]:
        """Return company metadata as a plain dictionary."""

        info = self._ticker(symbol).info
        return dict(info) if isinstance(info, Mapping) else {}

    def get_income_statement(self, symbol: str) -> Statement:
        """Return an income statement as nested plain dictionaries."""

        return self._normalize_statement(self._ticker(symbol).income_stmt)

    def get_cash_flow_statement(self, symbol: str) -> Statement:
        """Return a cash-flow statement as nested plain dictionaries."""

        return self._normalize_statement(self._ticker(symbol).cashflow)

    def _ticker(self, symbol: str) -> Any:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must be a non-empty string")

        if self._ticker_factory is not None:
            return self._ticker_factory(normalized_symbol)

        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - dependency failure
            raise RuntimeError(
                "The yfinance package is required. Install project dependencies "
                "from requirements.txt."
            ) from exc
        return yf.Ticker(normalized_symbol)

    @classmethod
    def _normalize_statement(cls, statement: Any) -> Statement:
        if statement is None or getattr(statement, "empty", False):
            return {}

        normalized: Statement = {}
        for row in statement.index:
            values = statement.loc[row]
            normalized[str(row)] = {
                str(date): cls._normalize_number(value)
                for date, value in values.items()
            }
        return normalized

    @staticmethod
    def _normalize_number(value: Any) -> float | None:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return None if math.isnan(number) else number
