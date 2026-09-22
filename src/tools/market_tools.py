"""Provider-independent tools for retrieving and processing market data.

These tools coordinate market-data adapters, beginning with Yahoo Finance,
without exposing provider-specific response formats to agents.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
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
    """Calculate return, volatility, and drawdown from closing prices."""

    close = [float(value) for value in client.get_history(symbol, period)]
    if not close:
        return {"error": f"No price data found for {symbol}"}
    if close[0] == 0:
        return {"error": f"Invalid starting price found for {symbol}"}

    start_price = close[0]
    latest_price = close[-1]
    total_return = (latest_price / start_price - 1) * 100

    daily_returns = [
        current / previous - 1
        for previous, current in zip(close, close[1:])
        if previous != 0
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
        "annualized_volatility_percent": (
            round(volatility, 2) if volatility is not None else None
        ),
        "maximum_drawdown_percent": round(min(drawdowns), 2),
        "observations": len(close),
    }


def get_company_info(
    client: MarketDataClient,
    symbol: str,
) -> dict[str, Any]:
    """Return the allow-listed company fields used by research agents."""

    info = client.get_company_info(symbol)
    return {field: info.get(field) for field in COMPANY_INFO_FIELDS}
