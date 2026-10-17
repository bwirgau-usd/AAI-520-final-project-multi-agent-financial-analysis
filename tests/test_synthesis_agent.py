"""Tests for final research report synthesis."""

import unittest

from src.agents.synthesis_agent import SynthesisAgent


class TestSynthesisAgent(unittest.TestCase):
    def test_prompt_requires_complete_grounded_report_coverage(self):
        prompts = []

        def llm(prompt):
            prompts.append(prompt)
            return "# AAPL Market Research"

        report = SynthesisAgent(llm).create_report(
            "AAPL",
            {
                "objectives": ["Review the company"],
                "tools": ["price_data"],
                "questions": ["What are the material risks?"],
            },
            {"price_data": {"latest_price": 200.0}},
            {
                "strengths": [],
                "weaknesses": [],
                "missing_information": [],
                "suspicious_values": [],
                "follow_up_questions": [],
                "deterministic_issues": [],
            },
            [],
        )

        self.assertTrue(report.startswith("# AAPL Market Research"))
        self.assertIn("**Latest Price**: $200.00", report)
        prompt = prompts[0]
        for required_detail in (
            "Company Overview",
            "Price Performance",
            "Valuation and",
            "Profitability",
            "Financial Performance",
            "Cash Flow",
            "SEC EDGAR Evidence",
            "CIK",
            "recent 10-K, 10-Q, and 8-K links",
            "Dividend",
            "Recent News and Catalysts",
            "routed specialist",
            "evaluator score and feedback",
            "optimized observations",
            "Risks and",
            "Uncertainties",
            "Data Quality",
            "Further Research",
            "price observation count",
            "EBITDA/net-income ratio",
            "dividend",
            "Do not use outside knowledge",
            "every numerical claim traceable",
            "Never claim a field is missing",
            "buy/sell/hold",
        ):
            with self.subTest(required_detail=required_detail):
                self.assertIn(required_detail, prompt)

    def test_reconciles_model_financial_values_with_provider_observations(self):
        def llm(_prompt):
            return """# Report

### Free Cash Flow
$987,670,000

### Capital Expenditure
-$127,150,000,000

### EBITDA/Net Income Ratio
1.277

### Dividend Yield
0.32
"""

        report = SynthesisAgent(llm).create_report(
            "AAPL",
            {"objectives": [], "tools": [], "questions": []},
            {
                "financials": {
                    "Net Income": {"2025-09-30": 112_010_000_000},
                    "EBITDA": {"2025-09-30": 144_748_000_000},
                },
                "cash_flow": {
                    "Free Cash Flow": {"2025-09-30": 98_767_000_000},
                    "Capital Expenditure": {"2025-09-30": -12_715_000_000},
                },
                "company_info": {"dividendYieldPercent": 0.32},
            },
            {
                "strengths": [],
                "weaknesses": [],
                "missing_information": [],
                "suspicious_values": [],
                "follow_up_questions": [],
                "deterministic_issues": [],
            },
            [],
        )

        self.assertNotIn("$987,670,000\n", report)
        self.assertNotIn("$127,150,000,000", report)
        self.assertNotIn("1.277", report)
        self.assertIn("$98,767,000,000", report)
        self.assertIn("-$12,715,000,000", report)
        self.assertIn("1.292x", report)
        self.assertIn("0.32%", report)

    def test_reconciles_market_scale_and_ratio_values(self):
        def llm(_prompt):
            return """# Report

- Market Capitalization: $50,125,167,569
- Latest Volume: 598,526,900
- Average Volume: 481,032,794
- Return on Equity: 14.88%
"""

        report = SynthesisAgent(llm).create_report(
            "AAPL",
            {"objectives": [], "tools": [], "questions": []},
            {
                "company_info": {
                    "marketCap": 5_012_516_765_696,
                    "returnOnEquity": 1.4875101,
                },
                "price_data": {
                    "latest_volume": 59_852_690,
                    "average_volume": 48_103_279.64,
                },
            },
            {
                "strengths": [],
                "weaknesses": [],
                "missing_information": [],
                "suspicious_values": [],
                "follow_up_questions": [],
                "deterministic_issues": [],
            },
            [],
        )

        self.assertNotIn("$50,125,167,569", report)
        self.assertNotIn("598,526,900", report)
        self.assertNotIn("481,032,794", report)
        self.assertNotIn("14.88%", report)
        self.assertIn("$5,012,516,765,696", report)
        self.assertIn("59,852,690", report)
        self.assertIn("48,103,280", report)
        self.assertIn("148.75%", report)


if __name__ == "__main__":
    unittest.main()
