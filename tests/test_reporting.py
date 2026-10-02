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

    def test_includes_every_notebook_final_report_detail(self):
        summary = render_console_summary(
            {
                "symbol": "NVDA",
                "plan": {
                    "objectives": ["Review financial performance"],
                    "tools": [
                        "price_data",
                        "company_info",
                        "financials",
                        "cash_flow",
                    ],
                    "questions": ["What could change the interpretation?"],
                },
                "observations": {
                    "price_data": {
                        "start_price": 177.27,
                        "latest_price": 224.78,
                        "1y_return_percent": 26.8,
                        "annualized_volatility_percent": 37.79,
                        "maximum_drawdown_percent": -20.21,
                        "observations": 252,
                    },
                    "company_info": {
                        "longName": "NVIDIA Corporation",
                        "sector": "Technology",
                        "industry": "Semiconductors",
                        "country": "United States",
                        "currentPrice": 224.78,
                        "marketCap": 5_000_000_000_000,
                        "enterpriseValue": 4_900_000_000_000,
                        "trailingPE": 45.2,
                        "forwardPE": 31.4,
                        "priceToSalesTrailing12Months": 22.1,
                        "profitMargins": 0.55,
                        "operatingMargins": 0.60,
                        "returnOnEquity": 0.95,
                        "beta": 1.67,
                        "dividendYield": 0.0003,
                    },
                    "financials": {
                        "Total Revenue": {"2026-01-31": 215_938_000_000},
                        "Operating Income": {"2026-01-31": 130_387_000_000},
                        "Net Income": {"2026-01-31": 120_067_000_000},
                        "EBITDA": {"2026-01-31": 144_552_000_000},
                        "Diluted EPS": {"2026-01-31": 4.9},
                    },
                    "cash_flow": {
                        "Operating Cash Flow": {
                            "2026-01-31": 102_718_000_000
                        },
                        "Free Cash Flow": {"2026-01-31": 96_676_000_000},
                        "Capital Expenditure": {"2026-01-31": -6_042_000_000},
                    },
                },
                "reflection": {
                    "strengths": ["Current market and financial data"],
                    "weaknesses": ["No news evidence"],
                    "missing_information": ["Recent company news"],
                    "suspicious_values": ["Verify capital expenditure"],
                    "follow_up_questions": ["What explains the valuation?"],
                    "deterministic_issues": [],
                },
                "validation": [
                    {
                        "type": "missing_metric",
                        "field": "news",
                        "message": "Recent news was not supplied.",
                    }
                ],
                "report_validation": [
                    {
                        "type": "coverage",
                        "field": "risk",
                        "message": "Risk discussion needs review.",
                    }
                ],
            }
        )

        expected_details = (
            "NVIDIA Corporation (NVDA)",
            "Sector:              Technology",
            "Industry:            Semiconductors",
            "Country:             United States",
            "Current Price:       $224.78",
            "Market Cap:          $5.000T",
            "Enterprise Value:    $4.900T",
            "Start Price:         $177.27",
            "Latest Price:        $224.78",
            "One-Year Return:     26.80%",
            "Annualized Volatility: 37.79%",
            "Maximum Drawdown:    -20.21%",
            "Observations:        252",
            "Trailing P/E:        45.20",
            "Forward P/E:         31.40",
            "Price/Sales (TTM):   22.10",
            "Profit Margin:       55.00%",
            "Operating Margin:    60.00%",
            "Return on Equity:    95.00%",
            "Beta:                1.670",
            "Revenue:             $215.938B",
            "Operating Income:    $130.387B",
            "Net Income:          $120.067B",
            "EBITDA:              $144.552B",
            "Diluted EPS:         $4.90",
            "EBITDA / Net Income: 1.204x",
            "Operating Cash Flow: $102.718B",
            "Free Cash Flow:      $96.676B",
            "Capital Expenditure: $-6.042B",
            "Dividend Yield:      0.03%",
            "7. RISKS AND UNCERTAINTIES",
            "No news evidence",
            "Verify capital expenditure",
            "8. DATA QUALITY",
            "Current market and financial data",
            "Recent news was not supplied.",
            "Risk discussion needs review.",
            "9. MISSING INFORMATION",
            "Recent company news",
            "10. FURTHER RESEARCH",
            "What explains the valuation?",
            "What could change the interpretation?",
        )
        for detail in expected_details:
            with self.subTest(detail=detail):
                self.assertIn(detail, summary)


if __name__ == "__main__":
    unittest.main()
