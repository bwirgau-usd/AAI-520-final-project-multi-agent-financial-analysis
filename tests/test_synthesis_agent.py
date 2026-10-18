"""Tests for final research report synthesis."""

import unittest

from src.agents.synthesis_agent import SynthesisAgent
from src.reporting.verified_metrics import append_verified_interpretation


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
            "operating expenses",
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

- Verified: All data is verified with official company filings and primary sources.
"""

        report = SynthesisAgent(llm).create_report(
            "AAPL",
            {"objectives": [], "tools": [], "questions": []},
            {
                "financials": {
                    "Operating Expenses": {
                        "2025-09-30": 274_891_000_000,
                    },
                    "Net Income": {"2025-09-30": 112_010_000_000},
                    "EBITDA": {"2025-09-30": 144_748_000_000},
                    "Diluted EPS": {"2025-09-30": 7.46},
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
        self.assertIn("**Operating Expenses** (2025-09-30): $274,891,000,000", report)
        self.assertIn("-$12,715,000,000", report)
        self.assertIn("1.292x", report)
        self.assertIn("0.32%", report)
        self.assertIn("**Diluted EPS** (2025-09-30): $7.46", report)
        self.assertNotIn("**Diluted EPS** (2025-09-30): $7\n", report)
        self.assertNotIn("All data is verified", report)
        self.assertIn(
            "SEC facts provide primary-source evidence for selected financial metrics",
            report,
        )

    def test_reconciles_yahoo_and_sec_equity_as_different_periods(self):
        report = SynthesisAgent(lambda _prompt: "# Report").create_report(
            "AAPL",
            {"objectives": [], "tools": [], "questions": []},
            {
                "balance_sheet": {
                    "latest": {"stockholders_equity": 73_733_000_000},
                    "trends": {"latest_period": "2025-09-30"},
                },
                "sec_edgar": {
                    "official_company_facts": {
                        "Stockholders Equity": {
                            "value": 107_520_000_000,
                            "fiscal_year": 2026,
                            "fiscal_period": "Q3",
                            "period_end": "2026-06-27",
                        }
                    },
                    "recent_filings": [],
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

        report = append_verified_interpretation(
            report,
            {
                "balance_sheet": {
                    "latest": {"stockholders_equity": 73_733_000_000},
                    "trends": {"latest_period": "2025-09-30"},
                },
                "sec_edgar": {
                    "official_company_facts": {
                        "Stockholders Equity": {
                            "value": 107_520_000_000,
                            "fiscal_year": 2026,
                            "fiscal_period": "Q3",
                            "period_end": "2026-06-27",
                        }
                    },
                    "recent_filings": [],
                },
            },
        )

        self.assertIn("$73,733,000,000 for 2025-09-30", report)
        self.assertIn("$107,520,000,000 for fiscal 2026 Q3 ended 2026-06-27", report)
        self.assertIn("different reporting periods", report)
        self.assertIn("## Verification Scope", report)
        self.assertIn(
            "Market data and news remain provider-supplied and require independent",
            report,
        )

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

    def test_report_exposes_saved_feedback_action_and_execution_evidence(self):
        lesson = {
            "weakness": "News analysis lacks financial implications",
            "next_run_action": (
                "Explain how each material event could affect revenue, costs, "
                "cash flow, or valuation"
            ),
            "success_check": (
                "Include supporting evidence, a financial implication, and uncertainty"
            ),
        }
        report = SynthesisAgent(lambda _prompt: "# Report").create_report(
            "AAPL",
            {
                "objectives": [],
                "tools": [],
                "questions": [],
                "applied_memory_actions": [lesson],
            },
            {
                "news_analysis": {
                    "articles": [
                        {
                            "evaluation": {
                                "substantive_reasoning_passed": True,
                            },
                            "optimized_analysis": {
                                "interpretation": (
                                    "The evidence does not establish a revenue or "
                                    "cash-flow effect, so uncertainty remains."
                                )
                            },
                        }
                    ]
                }
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

        self.assertIn("## Applied Prior-Run Feedback", report)
        self.assertIn(lesson["weakness"], report)
        self.assertIn(lesson["next_run_action"], report)
        self.assertIn("1 passed the substantive-reasoning check", report)
        self.assertIn("revenue or cash-flow effect", report)


if __name__ == "__main__":
    unittest.main()
