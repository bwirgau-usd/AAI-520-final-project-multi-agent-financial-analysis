"""Offline tests for deterministic company financial analysis."""

import unittest

from src.agents import FinancialAgent


class FakeFinancialAnalysisClient:
    def __init__(self):
        self.calls = []

    def get_income_statement(self, symbol):
        self.calls.append(("income", symbol))
        return {
            "Total Revenue": {"2025": 1_200.0, "2024": 1_000.0},
            "Gross Profit": {"2025": 600.0, "2024": 480.0},
            "Operating Income": {"2025": 240.0, "2024": 180.0},
            "Net Income": {"2025": 180.0, "2024": 150.0},
            "Diluted EPS": {"2025": 6.0, "2024": 5.0},
        }

    def get_balance_sheet(self, symbol):
        self.calls.append(("balance_sheet", symbol))
        return {
            "Cash Cash Equivalents And Short Term Investments": {
                "2025": 300.0,
                "2024": 250.0,
            },
            "Total Debt": {"2025": 180.0, "2024": 200.0},
            "Total Assets": {"2025": 1_500.0, "2024": 1_400.0},
            "Total Liabilities Net Minority Interest": {
                "2025": 600.0,
                "2024": 650.0,
            },
            "Stockholders Equity": {"2025": 900.0, "2024": 750.0},
        }

    def get_valuation(self, symbol):
        self.calls.append(("valuation", symbol))
        return {
            "Trailing P/E": {"Current": 25.0},
            "Forward P/E": {"Current": 20.0},
        }


class EmptyFinancialAnalysisClient:
    def get_income_statement(self, symbol):
        return {}

    def get_balance_sheet(self, symbol):
        return {}

    def get_valuation(self, symbol):
        return {}


class TestFinancialAgent(unittest.TestCase):
    def test_analyzes_income_valuation_and_balance_sheet_data(self):
        client = FakeFinancialAnalysisClient()
        agent = FinancialAgent(client)

        result = agent.analyze(" aapl ")

        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["revenue"]["value"], 1_200.0)
        self.assertEqual(result["revenue_growth_percent"], 20.0)
        self.assertEqual(result["net_income"]["value"], 180.0)
        self.assertEqual(result["earnings_growth_percent"], 20.0)
        self.assertEqual(result["eps"]["value"], 6.0)
        self.assertEqual(result["eps"]["growth_percent"], 20.0)
        self.assertEqual(result["margins"]["gross_margin"]["value_percent"], 50.0)
        self.assertEqual(
            result["margins"]["operating_margin"]["change_percentage_points"],
            2.0,
        )
        self.assertEqual(result["margins"]["net_margin"]["value_percent"], 15.0)
        self.assertEqual(result["pe"], {"trailing": 25.0, "forward": 20.0})
        self.assertEqual(result["cash"]["trend"], "increasing")
        self.assertEqual(result["debt"]["trend"], "decreasing")
        self.assertEqual(
            result["balance_sheet_trends"]["debt_to_equity"],
            0.2,
        )
        self.assertEqual(
            result["balance_sheet_trends"]["assets"]["direction"],
            "increasing",
        )
        self.assertEqual(result["data_gaps"], [])
        self.assertTrue(result["findings"])
        self.assertEqual(
            client.calls,
            [
                ("income", "AAPL"),
                ("balance_sheet", "AAPL"),
                ("valuation", "AAPL"),
            ],
        )

    def test_reports_data_gaps_without_fabricating_values(self):
        result = FinancialAgent(EmptyFinancialAnalysisClient()).analyze("MSFT")

        self.assertIsNone(result["revenue"]["value"])
        self.assertIsNone(result["earnings_growth_percent"])
        self.assertIsNone(result["pe"]["trailing"])
        self.assertEqual(result["findings"], [])
        self.assertIn("No usable revenue data was returned.", result["data_gaps"])
        self.assertIn("No usable debt data was returned.", result["data_gaps"])

    def test_rejects_blank_symbol_before_fetching_data(self):
        client = FakeFinancialAnalysisClient()

        with self.assertRaisesRegex(ValueError, "non-empty"):
            FinancialAgent(client).analyze(" ")

        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
