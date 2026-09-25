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
                    "company_info": {"longName": "Apple Inc."},
                    "financials": {
                        "Total Revenue": {
                            "2025-09-30": 2_000_000_000,
                            "2024-09-30": 1_800_000_000,
                        }
                    },
                    "cash_flow": {
                        "Free Cash Flow": {"2025-09-30": 500_000_000}
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
        self.assertIn("Free Cash Flow:      $500.000M", summary)


if __name__ == "__main__":
    unittest.main()
