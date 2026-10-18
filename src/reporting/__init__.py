"""Presentation helpers kept separate from research orchestration."""

from .charts import (
    StockPriceChart,
    plot_10_year_stock_price,
    plot_operating_expenses,
    plot_revenue_and_operating_expenses,
)
from .console import render_console_summary
from .diagrams import (
    plot_news_analysis_summary,
    plot_news_workflow,
    plot_system_architecture,
)
from .requirements import build_requirement_traceability

__all__ = [
    "StockPriceChart",
    "build_requirement_traceability",
    "plot_10_year_stock_price",
    "plot_news_analysis_summary",
    "plot_news_workflow",
    "plot_operating_expenses",
    "plot_revenue_and_operating_expenses",
    "plot_system_architecture",
    "render_console_summary",
]
