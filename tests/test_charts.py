"""Tests for stock-price chart presentation."""

import unittest
from datetime import datetime, timezone

from matplotlib import pyplot as plt

from src.data_sources.base import PricePoint
from src.reporting import plot_10_year_stock_price


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


if __name__ == "__main__":
    unittest.main()
