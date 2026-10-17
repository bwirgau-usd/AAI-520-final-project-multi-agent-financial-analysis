"""Provider-independent tools for retrieving and processing market data.

These tools coordinate market-data adapters, beginning with Yahoo Finance,
without exposing provider-specific response formats to agents.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import Any, Protocol

COMPANY_INFO_FIELDS = (
    "longName",
    "sector",
    "industry",
    "country",
    "marketCap",
    "enterpriseValue",
    "currentPrice",
    "trailingPE",
    "forwardPE",
    "priceToSalesTrailing12Months",
    "profitMargins",
    "operatingMargins",
    "returnOnEquity",
    "beta",
    "dividendYield",
    "totalCash",
    "totalDebt",
)


class MarketDataClient(Protocol):
    """Data-source operations required by the market tools."""

    def get_history(self, symbol: str, period: str = "1y") -> Sequence[float]:
        """Return closing prices for a symbol and period."""

    def get_company_info(self, symbol: str) -> Mapping[str, Any]:
        """Return company metadata."""


def get_price_data(
    client: MarketDataClient,
    symbol: str,
    period: str = "1y",
) -> dict[str, Any]:
    """Calculate performance, risk, range, and trading-volume metrics."""

    get_market_history = getattr(client, "get_market_history", None)
    history = get_market_history(symbol, period) if callable(get_market_history) else {}
    raw_close = (
        history.get("close", [])
        if callable(get_market_history) and isinstance(history, Mapping)
        else client.get_history(symbol, period)
    )
    close = [float(value) for value in raw_close]
    if not close:
        return {"error": f"No price data found for {symbol}"}
    if close[0] == 0:
        return {"error": f"Invalid starting price found for {symbol}"}

    start_price = close[0]
    latest_price = close[-1]
    total_return = (latest_price / start_price - 1) * 100

    daily_returns = [
        current / previous - 1 for previous, current in pairwise(close) if previous != 0
    ]
    volatility = (
        statistics.stdev(daily_returns) * math.sqrt(252) * 100
        if len(daily_returns) >= 2
        else None
    )

    running_max = close[0]
    drawdowns: list[float] = []
    for price in close:
        running_max = max(running_max, price)
        drawdowns.append((price / running_max - 1) * 100)

    return {
        "start_price": round(start_price, 2),
        "latest_price": round(latest_price, 2),
        "1y_return_percent": round(total_return, 2),
        "1m_return_percent": _period_return(close, 21),
        "3m_return_percent": _period_return(close, 63),
        "annualized_volatility_percent": (
            round(volatility, 2) if volatility is not None else None
        ),
        "maximum_drawdown_percent": round(min(drawdowns), 2),
        "52_week_high": _series_extreme(history, "high", max, close),
        "52_week_low": _series_extreme(history, "low", min, close),
        "latest_volume": _latest_series_value(history, "volume"),
        "average_volume": _average_series_value(history, "volume"),
        "observations": len(close),
    }


def _period_return(close: Sequence[float], trading_days: int) -> float | None:
    if len(close) <= trading_days or close[-(trading_days + 1)] == 0:
        return None
    value = (close[-1] / close[-(trading_days + 1)] - 1) * 100
    return round(value, 2)


def _series_extreme(
    history: object,
    field: str,
    operation: Any,
    fallback: Sequence[float],
) -> float | None:
    values = history.get(field, []) if isinstance(history, Mapping) else []
    candidates = [float(value) for value in values] or list(fallback)
    return round(float(operation(candidates)), 2) if candidates else None


def _latest_series_value(history: object, field: str) -> float | None:
    values = history.get(field, []) if isinstance(history, Mapping) else []
    return round(float(values[-1]), 2) if values else None


def _average_series_value(history: object, field: str) -> float | None:
    values = history.get(field, []) if isinstance(history, Mapping) else []
    return round(statistics.fmean(float(value) for value in values), 2) if values else None


def get_company_info(
    client: MarketDataClient,
    symbol: str,
) -> dict[str, Any]:
    """Return the allow-listed company fields used by research agents."""

    info = client.get_company_info(symbol)
    result = {field: info.get(field) for field in COMPANY_INFO_FIELDS}
    # Yahoo Finance's ``dividendYield`` display value is already expressed in
    # percentage points (for example, 0.32 means 0.32%, not 32%). Keep the raw
    # field for compatibility and expose its unit explicitly for report code.
    result["dividendYieldPercent"] = info.get("dividendYield")
    result["dividendYieldUnit"] = "percent"
    return result
