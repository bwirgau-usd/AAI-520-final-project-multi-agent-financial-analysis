"""Chart presentation for market-data observations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from matplotlib import pyplot as plt
from matplotlib.figure import Figure

from src.data_sources.base import PricePoint


class PriceHistoryClient(Protocol):
    """Data-source operation required by the stock-price chart."""

    def get_price_history(
        self,
        symbol: str,
        period: str = "10y",
    ) -> Sequence[PricePoint]:
        """Return dated closing prices for a symbol and period."""


@dataclass(frozen=True)
class StockPriceChart:
    """The rendered chart and its deterministic summary values."""

    figure: Figure
    start_price: float
    end_price: float
    total_return_percent: float | None

    @property
    def summary(self) -> str:
        """Render the concise summary shown below the chart."""

        if self.total_return_percent is None:
            return (
                "10-year price summary: "
                f"${self.start_price:,.2f} → ${self.end_price:,.2f} (N/A)"
            )
        return (
            "10-year price summary: "
            f"${self.start_price:,.2f} → ${self.end_price:,.2f} "
            f"({self.total_return_percent:+,.1f}%)"
        )


def plot_10_year_stock_price(
    client: PriceHistoryClient,
    symbol: str,
    *,
    show: bool = True,
) -> StockPriceChart | None:
    """Build a 10-year adjusted stock-price chart.

    The caller supplies the data client so this presentation helper remains
    independent of Yahoo Finance and can be exercised without network access.
    ``None`` is returned when the provider has no usable history.
    """

    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must be a non-empty string")

    history = list(client.get_price_history(normalized_symbol, period="10y"))
    if not history:
        return None

    dates = [point.date for point in history]
    prices = [float(point.close) for point in history]

    figure, axes = plt.subplots(figsize=(12, 5.5))
    axes.plot(dates, prices, linewidth=2)
    axes.set_title(
        f"{normalized_symbol} — 10-Year Stock Price",
        fontsize=15,
        fontweight="bold",
    )
    axes.set_xlabel("Date")
    axes.set_ylabel("Adjusted Close Price (USD)")
    axes.grid(True, alpha=0.25)
    axes.margins(x=0)
    figure.tight_layout()

    start_price = prices[0]
    end_price = prices[-1]
    total_return = (
        None
        if start_price == 0
        else ((end_price / start_price) - 1) * 100
    )
    result = StockPriceChart(
        figure=figure,
        start_price=start_price,
        end_price=end_price,
        total_return_percent=total_return,
    )

    if show:
        plt.show()
    return result
