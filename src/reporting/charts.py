"""Chart presentation for market-data observations."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from numbers import Number
from typing import Protocol

from matplotlib import pyplot as plt
from matplotlib.figure import Figure

from src.data_sources.base import PricePoint
from src.tools.financial_tools import derive_operating_expenses


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
    total_return = None if start_price == 0 else ((end_price / start_price) - 1) * 100
    result = StockPriceChart(
        figure=figure,
        start_price=start_price,
        end_price=end_price,
        total_return_percent=total_return,
    )

    if show:
        plt.show()
    return result


def plot_revenue_and_operating_expenses(
    financials: Mapping[str, Mapping[str, float | None]],
    symbol: str,
    *,
    show: bool = True,
) -> Figure | None:
    """Plot revenue beside operating expenses for up to five fiscal periods."""

    normalized_symbol = _normalized_symbol(symbol)
    revenue = _statement_series(
        financials,
        ("Total Revenue", "Operating Revenue", "Revenue"),
    )
    expenses = derive_operating_expenses(financials)
    periods = _latest_periods(list(revenue))
    if not periods or not revenue:
        return None

    revenue_values = [_billions(revenue.get(period)) for period in periods]
    expense_values = [_billions(expenses.get(period)) for period in periods]
    positions = list(range(len(periods)))
    width = 0.38
    figure, axes = plt.subplots(figsize=(11, 6))
    revenue_bars = axes.bar(
        [position - width / 2 for position in positions],
        revenue_values,
        width,
        label="Revenue",
        color="#2878B5",
    )
    _label_bars(axes, revenue_bars)
    if expenses:
        expense_bars = axes.bar(
            [position + width / 2 for position in positions],
            expense_values,
            width,
            label="Operating Expenses",
            color="#E07A3F",
        )
        _label_bars(axes, expense_bars)

    axes.set_title(
        f"{normalized_symbol} — Revenue and Operating Expenses",
        fontsize=15,
        fontweight="bold",
    )
    axes.set_xlabel("Fiscal Period")
    axes.set_ylabel("USD Billions")
    axes.set_xticks(positions, [_period_label(period) for period in periods])
    axes.grid(axis="y", alpha=0.25)
    axes.set_axisbelow(True)
    axes.legend()
    figure.tight_layout()
    if show:
        plt.show()
    return figure


def plot_operating_expenses(
    financials: Mapping[str, Mapping[str, float | None]],
    symbol: str,
    *,
    show: bool = True,
) -> Figure | None:
    """Plot operating-expense history for up to five fiscal periods."""

    normalized_symbol = _normalized_symbol(symbol)
    expenses = derive_operating_expenses(financials)
    periods = _latest_periods(list(expenses))
    if not periods:
        return None

    figure, axes = plt.subplots(figsize=(11, 5.5))
    bars = axes.bar(
        [_period_label(period) for period in periods],
        [_billions(expenses[period]) for period in periods],
        color="#E07A3F",
        width=0.65,
    )
    _label_bars(axes, bars)
    axes.set_title(
        f"{normalized_symbol} — Operating Expenses",
        fontsize=15,
        fontweight="bold",
    )
    axes.set_xlabel("Fiscal Period")
    axes.set_ylabel("USD Billions")
    axes.grid(axis="y", alpha=0.25)
    axes.set_axisbelow(True)
    figure.tight_layout()
    if show:
        plt.show()
    return figure


def _statement_series(
    statement: Mapping[str, Mapping[str, float | None]],
    row_names: tuple[str, ...],
) -> dict[str, float]:
    normalized = {
        str(row).strip().casefold(): values for row, values in statement.items()
    }
    for name in row_names:
        values = normalized.get(name.casefold())
        if not isinstance(values, Mapping):
            continue
        return {
            str(period): float(value)
            for period, value in values.items()
            if isinstance(value, Number) and not isinstance(value, bool)
        }
    return {}


def _latest_periods(periods: Sequence[str], limit: int = 5) -> list[str]:
    unique_periods = list(dict.fromkeys(str(period) for period in periods))
    return sorted(unique_periods, key=_period_sort_key)[-limit:]


def _period_sort_key(period: str) -> tuple[int, float | str]:
    try:
        return 1, datetime.fromisoformat(period).timestamp()
    except (ValueError, OverflowError):
        return 0, period


def _period_label(period: str) -> str:
    try:
        parsed = datetime.fromisoformat(period)
    except ValueError:
        return period
    return str(parsed.year)


def _billions(value: float | None) -> float:
    return float("nan") if value is None else value / 1_000_000_000


def _label_bars(axes: object, bars: object) -> None:
    bar_label = getattr(axes, "bar_label", None)
    if callable(bar_label):
        labels = []
        for bar in bars:
            height = float(bar.get_height())
            labels.append(f"${height:.1f}B" if math.isfinite(height) else "")
        bar_label(bars, labels=labels, padding=3, fontsize=8)


def _normalized_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("symbol must be a non-empty string")
    return normalized
