"""Offline tests for provider-independent market tools."""

import math
import statistics
import unittest

from src.tools.market_tools import get_company_info, get_price_data


class FakeMarketClient:
    def __init__(self, prices):
        self.prices = prices
        self.calls = []

    def get_history(self, symbol, period="1y"):
        self.calls.append((symbol, period))
        return self.prices

    def get_company_info(self, symbol):
        return {
            "longName": "Example Corp",
            "sector": "Technology",
            "marketCap": 1000,
            "unrequested": "excluded",
        }


class TestMarketTools(unittest.TestCase):
    def test_calculates_price_metrics(self):
        client = FakeMarketClient([100, 110, 99])

        result = get_price_data(client, "AAPL", period="6mo")

        expected_volatility = statistics.stdev([0.1, -0.1]) * math.sqrt(252) * 100
        self.assertEqual(result["start_price"], 100.0)
        self.assertEqual(result["latest_price"], 99.0)
        self.assertEqual(result["1y_return_percent"], -1.0)
        self.assertEqual(
            result["annualized_volatility_percent"],
            round(expected_volatility, 2),
        )
        self.assertEqual(result["maximum_drawdown_percent"], -10.0)
        self.assertEqual(result["observations"], 3)
        self.assertEqual(client.calls, [("AAPL", "6mo")])

    def test_returns_error_when_prices_are_unavailable(self):
        result = get_price_data(FakeMarketClient([]), "MISSING")

        self.assertEqual(result, {"error": "No price data found for MISSING"})

    def test_filters_company_fields(self):
        result = get_company_info(FakeMarketClient([]), "AAPL")

        self.assertEqual(result["longName"], "Example Corp")
        self.assertEqual(result["marketCap"], 1000)
        self.assertNotIn("unrequested", result)
        self.assertIn("dividendYield", result)

    def test_calculates_period_range_and_volume_metrics(self):
        class RichMarketClient(FakeMarketClient):
            def get_market_history(self, symbol, period="1y"):
                close = [float(value) for value in range(100, 171)]
                return {
                    "close": close,
                    "high": [value + 2 for value in close],
                    "low": [value - 3 for value in close],
                    "volume": [1_000 + value for value in range(len(close))],
                }

        result = get_price_data(RichMarketClient([]), "AAPL")

        self.assertEqual(result["1m_return_percent"], 14.09)
        self.assertEqual(result["3m_return_percent"], 58.88)
        self.assertEqual(result["52_week_high"], 172.0)
        self.assertEqual(result["52_week_low"], 97.0)
        self.assertEqual(result["latest_volume"], 1070.0)
        self.assertEqual(result["average_volume"], 1035.0)
