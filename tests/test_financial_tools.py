"""Offline tests for provider-independent financial tools."""

import unittest

from src.tools.financial_tools import (
    get_balance_sheet,
    get_cash_flow,
    get_financial_growth,
    get_financials,
)


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

    def get_balance_sheet(self, symbol):
        return {
            "Cash And Cash Equivalents": {"2025": 125.0},
            "Total Debt": {"2025": 50.0},
            "Total Assets": {"2025": 800.0},
            "Stockholders Equity": {"2025": 300.0},
        }


class EmptyFinancialClient:
    def get_income_statement(self, symbol):
        return {}

    def get_cash_flow_statement(self, symbol):
        return {}

    def get_balance_sheet(self, symbol):
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

    def test_calculates_balance_sheet_cash_and_debt(self):
        result = get_balance_sheet(FakeFinancialClient(), "AAPL")

        self.assertEqual(result["latest"]["cash"], 125.0)
        self.assertEqual(result["latest"]["debt"], 50.0)
        self.assertEqual(result["latest"]["net_debt"], -75.0)
        self.assertEqual(result["latest"]["cash_to_debt_ratio"], 2.5)

    def test_calculates_revenue_and_earnings_growth(self):
        result = get_financial_growth(FakeFinancialClient(), "AAPL")

        self.assertEqual(result["revenue_growth_percent"], 11.11)
        self.assertIsNone(result["net_income_growth_percent"])
        self.assertEqual(result["latest_period"], "2025")
