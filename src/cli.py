"""Optional command-line entry point for the research workflow."""

from __future__ import annotations

from src.data_sources.yahoo_finance import YahooFinanceClient
from src.reporting import (
    plot_10_year_stock_price,
    plot_news_analysis_summary,
    render_console_summary,
)
from src.workflows import build_research_workflow


def main() -> None:
    """Prompt for a ticker, run the workflow, and print its report."""

    symbol = input("Stock symbol: ").strip()
    workflow = build_research_workflow()
    result = workflow.run(symbol, progress=print)
    print()
    print(render_console_summary(result))
    print()
    print(result["report"])
    print()
    print("NEWS ANALYSIS SUMMARY")
    news_chart = plot_news_analysis_summary(result.get("news_analysis", {}))
    if news_chart is None:
        print("No news articles were available for the summary graph.")
    print()
    print("10-YEAR STOCK PRICE")
    try:
        chart = plot_10_year_stock_price(
            YahooFinanceClient(),
            result["symbol"],
        )
    except Exception as exc:  # noqa: BLE001 - keep reporting failures isolated
        print(f"Could not display 10-year stock chart: {type(exc).__name__}: {exc}")
    else:
        if chart is None:
            print("No 10-year price history was available.")
        else:
            print(chart.summary)


if __name__ == "__main__":  # pragma: no cover - interactive entry point
    main()
