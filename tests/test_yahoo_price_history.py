"""Tests for dated Yahoo Finance price history."""

import unittest
from datetime import datetime, timezone

from src.data_sources.yahoo_finance import YahooFinanceClient


class FakeColumn:
    def __init__(self, observations):
        self.observations = observations

    def dropna(self):
        return FakeColumn(
            [
                (date, value)
                for date, value in self.observations
                if value is not None
            ]
        )

    def items(self):
        return iter(self.observations)


class FakeHistory:
    empty = False

    def __contains__(self, key):
        return key == "Close"

    def __getitem__(self, key):
        if key != "Close":
            raise KeyError(key)
        return FakeColumn(
            [
                (datetime(2016, 1, 4, tzinfo=timezone.utc), 100),
                (datetime(2016, 1, 5, tzinfo=timezone.utc), None),
                (datetime(2026, 1, 2, tzinfo=timezone.utc), 110),
            ]
        )


class FakeTicker:
    def __init__(self):
        self.requests = []

    def history(self, **request):
        self.requests.append(request)
        return FakeHistory()


class TestYahooPriceHistory(unittest.TestCase):
    def test_returns_dated_adjusted_history_for_charting(self):
        symbols = []
        ticker = FakeTicker()

        def ticker_factory(symbol):
            symbols.append(symbol)
            return ticker

        client = YahooFinanceClient(ticker_factory)

        history = client.get_price_history(" aapl ")

        self.assertEqual(
            [(point.date, point.close) for point in history],
            [
                (datetime(2016, 1, 4, tzinfo=timezone.utc), 100.0),
                (datetime(2026, 1, 2, tzinfo=timezone.utc), 110.0),
            ],
        )
        self.assertEqual(symbols, ["AAPL"])
        self.assertEqual(
            ticker.requests,
            [{"period": "10y", "auto_adjust": True}],
        )


if __name__ == "__main__":
    unittest.main()
