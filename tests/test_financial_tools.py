"""Offline tests for provider-independent financial tools."""

import unittest

from src.tools.financial_tools import get_cash_flow, get_financials


class FakeFinancialClient:
    def get_income_statement(self, symbol):
        return {
            "Total Revenue": {
                "2025": 500.0,
                "2024": 450.0,
                "2023": 400.0,
                "2022": 350.0,
                "2021": 300.0,
            },
            "Net Income": {"2025": 75.0},
            "Ignored Row": {"2025": 1.0},
        }

    def get_cash_flow_statement(self, symbol):
        return {
            "Operating Cash Flow": {"2025": 100.0},
            "Free Cash Flow": {"2025": 80.0},
        }


class EmptyFinancialClient:
    def get_income_statement(self, symbol):
        return {}

    def get_cash_flow_statement(self, symbol):
        return {}


class TestFinancialTools(unittest.TestCase):
    def test_selects_income_rows_and_limits_periods(self):
        result = get_financials(FakeFinancialClient(), "AAPL")

        self.assertEqual(list(result), ["Total Revenue", "Net Income"])
        self.assertEqual(
            list(result["Total Revenue"]),
            ["2025", "2024", "2023", "2022"],
        )

    def test_selects_cash_flow_rows(self):
        result = get_cash_flow(FakeFinancialClient(), "AAPL")

        self.assertEqual(
            result,
            {
                "Operating Cash Flow": {"2025": 100.0},
                "Free Cash Flow": {"2025": 80.0},
            },
        )

    def test_returns_errors_for_empty_statements(self):
        client = EmptyFinancialClient()

        self.assertEqual(
            get_financials(client, "AAPL"),
            {"error": "No financial statements found"},
        )
        self.assertEqual(
            get_cash_flow(client, "AAPL"),
            {"error": "No cash-flow data found"},
        )

