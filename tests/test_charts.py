"""Tests for stock-price chart presentation."""

import unittest
from datetime import datetime, timezone

from matplotlib import pyplot as plt

from src.data_sources.base import PricePoint
from src.reporting import (
    plot_10_year_stock_price,
    plot_news_analysis_summary,
    plot_news_workflow,
    plot_operating_expenses,
    plot_revenue_and_operating_expenses,
    plot_system_architecture,
)


class FakePriceHistoryClient:
    def __init__(self, history):
        self.history = history
        self.calls = []

    def get_price_history(self, symbol, period="10y"):
        self.calls.append((symbol, period))
        return self.history


class TestStockPriceChart(unittest.TestCase):
    def tearDown(self):
        plt.close("all")

    def test_plots_history_and_calculates_summary(self):
        client = FakePriceHistoryClient(
            [
                PricePoint(datetime(2016, 1, 4, tzinfo=timezone.utc), 100.0),
                PricePoint(datetime(2026, 1, 2, tzinfo=timezone.utc), 175.0),
            ]
        )

        chart = plot_10_year_stock_price(client, " aapl ", show=False)

        self.assertIsNotNone(chart)
        self.assertEqual(client.calls, [("AAPL", "10y")])
        self.assertEqual(chart.start_price, 100.0)
        self.assertEqual(chart.end_price, 175.0)
        self.assertEqual(chart.total_return_percent, 75.0)
        self.assertEqual(
            chart.summary,
            "10-year price summary: $100.00 → $175.00 (+75.0%)",
        )

        axes = chart.figure.axes[0]
        self.assertEqual(axes.get_title(), "AAPL — 10-Year Stock Price")
        self.assertEqual(axes.get_xlabel(), "Date")
        self.assertEqual(axes.get_ylabel(), "Adjusted Close Price (USD)")
        self.assertEqual(list(axes.lines[0].get_ydata()), [100.0, 175.0])

    def test_returns_none_when_history_is_unavailable(self):
        client = FakePriceHistoryClient([])

        chart = plot_10_year_stock_price(client, "MSFT", show=False)

        self.assertIsNone(chart)
        self.assertEqual(client.calls, [("MSFT", "10y")])

    def test_rejects_blank_symbol_without_calling_provider(self):
        client = FakePriceHistoryClient([])

        with self.assertRaisesRegex(ValueError, "non-empty"):
            plot_10_year_stock_price(client, " ", show=False)

        self.assertEqual(client.calls, [])


class TestReportDiagrams(unittest.TestCase):
    def tearDown(self):
        plt.close("all")

    def test_system_architecture_contains_implemented_components(self):
        figure = plot_system_architecture(show=False)

        labels = {text.get_text() for text in figure.axes[0].texts}
        self.assertIn("Planner", labels)
        self.assertIn("Request\nRouter", labels)
        self.assertIn("News Prompt Chain\n+ Specialists", labels)
        self.assertIn("Report\nEvaluator", labels)
        self.assertIn("Report\nOptimizer", labels)
        self.assertIn("Final Report\n+ Visuals", labels)

    def test_news_workflow_contains_required_patterns(self):
        figure = plot_news_workflow(show=False)

        labels = {text.get_text() for text in figure.axes[0].texts}
        for expected in ("Preprocess", "Route", "Specialist", "Evaluate", "Optimize"):
            with self.subTest(expected=expected):
                self.assertIn(expected, labels)

    def test_plots_news_source_routing_and_scores(self):
        figure = plot_news_analysis_summary(
            {
                "ticker": "AAPL",
                "source_counts": {"Yahoo Finance": 1},
                "routing_counts": {"earnings": 1},
                "evaluation_threshold": 75,
                "articles": [{"evaluation": {"score": 100}}],
            },
            show=False,
        )

        self.assertIsNotNone(figure)
        self.assertEqual(len(figure.axes), 3)
        self.assertEqual(figure.axes[0].get_title(), "Articles by Source")
        self.assertEqual(figure.axes[2].get_title(), "Final Evaluation Scores")

    def test_skips_news_chart_without_articles(self):
        self.assertIsNone(plot_news_analysis_summary({"articles": []}, show=False))


class TestFinancialCharts(unittest.TestCase):
    def tearDown(self):
        plt.close("all")

    def test_plots_revenue_and_operating_expenses_in_chronological_order(self):
        financials = {
            "Total Revenue": {
                "2025-09-30": 500_000_000_000.0,
                "2024-09-30": 450_000_000_000.0,
            },
            "Operating Expenses": {
                "2025-09-30": 200_000_000_000.0,
                "2024-09-30": 180_000_000_000.0,
            },
        }

        figure = plot_revenue_and_operating_expenses(
            financials,
            " aapl ",
            show=False,
        )

        self.assertIsNotNone(figure)
        axes = figure.axes[0]
        self.assertEqual(
            axes.get_title(),
            "AAPL — Revenue and Operating Expenses",
        )
        self.assertEqual(axes.get_ylabel(), "USD Billions")
        self.assertEqual(
            [label.get_text() for label in axes.get_xticklabels()],
            ["2024", "2025"],
        )
        self.assertEqual(len(axes.patches), 4)

    def test_plots_standalone_operating_expense_history(self):
        figure = plot_operating_expenses(
            {
                "Operating Expenses": {
                    "2025": 200_000_000_000.0,
                    "2024": 180_000_000_000.0,
                }
            },
            "MSFT",
            show=False,
        )

        self.assertIsNotNone(figure)
        axes = figure.axes[0]
        self.assertEqual(axes.get_title(), "MSFT — Operating Expenses")
        self.assertEqual(
            [bar.get_height() for bar in axes.patches],
            [180.0, 200.0],
        )

    def test_skips_financial_charts_without_required_data(self):
        self.assertIsNone(
            plot_revenue_and_operating_expenses({}, "AAPL", show=False)
        )
        self.assertIsNone(plot_operating_expenses({}, "AAPL", show=False))


if __name__ == "__main__":
    unittest.main()
