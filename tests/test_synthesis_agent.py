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

        self.assertEqual(report, "# AAPL Market Research")
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


if __name__ == "__main__":
    unittest.main()
