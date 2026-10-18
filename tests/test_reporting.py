"""Tests for deterministic result presentation."""

import unittest

from src.reporting import render_console_summary


class TestConsoleReporting(unittest.TestCase):
    def test_formats_key_workflow_artifacts(self):
        summary = render_console_summary(
            {
                "symbol": "AAPL",
                "plan": {
                    "objectives": [],
                    "tools": ["price_data"],
                    "questions": [],
                },
                "observations": {
                    "price_data": {
                        "latest_price": 201.5,
                        "1y_return_percent": 12.25,
                    },
                    "company_info": {
                        "longName": "Apple Inc.",
                        "dividendYieldPercent": 0.32,
                    },
                    "financials": {
                        "Total Revenue": {
                            "2025-09-30": 2_000_000_000,
                            "2024-09-30": 1_800_000_000,
                        },
                        "Operating Expenses": {
                            "2025-09-30": 750_000_000,
                        },
                    },
                    "cash_flow": {
                        "Free Cash Flow": {"2025-09-30": 500_000_000},
                        "Capital Expenditure": {"2025-09-30": -12_715_000_000},
                    },
                    "balance_sheet": {
                        "latest": {
                            "cash": 50_000_000_000,
                            "debt": 100_000_000_000,
                            "net_debt": 50_000_000_000,
                            "cash_to_debt_ratio": 0.5,
                            "total_assets": 300_000_000_000,
                            "total_liabilities": 200_000_000_000,
                            "stockholders_equity": 100_000_000_000,
                        },
                        "trends": {
                            "cash_growth_percent": 5.0,
                            "debt_growth_percent": -2.0,
                            "assets_growth_percent": 4.0,
                        },
                    },
                    "financial_growth": {
                        "revenue_growth_percent": 11.11,
                        "net_income_growth_percent": 8.5,
                        "diluted_eps_growth_percent": 9.25,
                    },
                },
                "reflection": {
                    "strengths": [],
                    "weaknesses": [],
                    "missing_information": [],
                    "suspicious_values": [],
                    "follow_up_questions": [],
                    "deterministic_issues": [],
                },
                "validation": [],
                "report_validation": [],
            }
        )

        self.assertIn("FINAL RESEARCH REPORT", summary)
        self.assertIn("Apple Inc. (AAPL)", summary)
        self.assertIn("Current Price:       $201.50", summary)
        self.assertIn("One-Year Return:     12.25%", summary)
        self.assertIn("FINANCIAL PERFORMANCE (2025)", summary)
        self.assertIn("Revenue:             $2.000B", summary)
        self.assertIn("Operating Expenses:  $750.000M", summary)
        self.assertIn("Free Cash Flow:      $500.000M", summary)
        self.assertIn("Capital Expenditure: -$12.715B", summary)
        self.assertIn("BALANCE SHEET AND GROWTH", summary)
        self.assertIn("Cash:                $50.000B", summary)
        self.assertIn("Total Debt:          $100.000B", summary)
        self.assertIn("Revenue Growth:      11.11%", summary)
        self.assertIn("Cash Trend:          5.00%", summary)
        self.assertIn("Dividend Yield:      0.32%", summary)


if __name__ == "__main__":
    unittest.main()
