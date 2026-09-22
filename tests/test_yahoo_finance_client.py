"""Offline tests for the Yahoo Finance provider adapter."""

import math
import unittest

from src.data_sources.yahoo_finance import YahooFinanceClient


class FakeColumn(list):
    def dropna(self):
        return FakeColumn(value for value in self if value is not None)


class FakeHistory:
    def __init__(self, close=None):
        self._close = close
        self.empty = close is None

    def __contains__(self, key):
        return key == "Close" and self._close is not None

    def __getitem__(self, key):
        if key != "Close" or self._close is None:
            raise KeyError(key)
        return FakeColumn(self._close)


class FakeRow:
    def __init__(self, values):
        self._values = values

    def items(self):
        return self._values.items()


class FakeLoc:
    def __init__(self, rows):
        self._rows = rows

    def __getitem__(self, row):
        return FakeRow(self._rows[row])


class FakeStatement:
    def __init__(self, rows):
        self._rows = rows
        self.empty = not rows
        self.index = list(rows)
        self.loc = FakeLoc(rows)


class FakeTicker:
    def __init__(self):
        self.history_periods = []
        self.info = {"longName": "Example Corp", "marketCap": 1000}
        self.income_stmt = FakeStatement(
            {"Total Revenue": {"2025": 500, "2024": math.nan}}
        )
        self.cashflow = FakeStatement(
            {"Free Cash Flow": {"2025": 125}}
        )

    def history(self, *, period):
        self.history_periods.append(period)
        return FakeHistory([100, None, 110])


class TestYahooFinanceClient(unittest.TestCase):
    def setUp(self):
        self.symbols = []
        self.ticker = FakeTicker()

        def ticker_factory(symbol):
            self.symbols.append(symbol)
            return self.ticker

        self.client = YahooFinanceClient(ticker_factory)

    def test_normalizes_symbol_and_closing_prices(self):
        prices = self.client.get_history(" aapl ", period="5d")

        self.assertEqual(prices, [100.0, 110.0])
        self.assertEqual(self.symbols, ["AAPL"])
        self.assertEqual(self.ticker.history_periods, ["5d"])

    def test_returns_plain_company_info(self):
        info = self.client.get_company_info("AAPL")

        self.assertEqual(info["longName"], "Example Corp")
        self.assertIsNot(info, self.ticker.info)

    def test_normalizes_statements_and_missing_values(self):
        income = self.client.get_income_statement("AAPL")
        cash_flow = self.client.get_cash_flow_statement("AAPL")

        self.assertEqual(
            income,
            {"Total Revenue": {"2025": 500.0, "2024": None}},
        )
        self.assertEqual(cash_flow, {"Free Cash Flow": {"2025": 125.0}})

    def test_rejects_blank_symbol(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            self.client.get_company_info(" ")

