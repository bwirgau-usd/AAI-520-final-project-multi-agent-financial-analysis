"""Presentation helpers kept separate from research orchestration."""

from .charts import StockPriceChart, plot_10_year_stock_price
from .console import render_console_summary

__all__ = [
    "StockPriceChart",
    "plot_10_year_stock_price",
    "render_console_summary",
]
