"""Offline tests for deterministic and model-assisted evaluation."""

import json
import unittest

from src.agents.evaluator import EvaluatorAgent


class TestEvaluatorAgent(unittest.TestCase):
    def test_accepts_actual_one_year_return_key(self):
        evaluator = EvaluatorAgent(lambda _prompt: "{}")
        observations = {
            "price_data": {
                "latest_price": 200.0,
                "1y_return_percent": 12.5,
            }
        }

        issues = evaluator.validate_observations(observations)

        missing_fields = {
            issue.get("field")
            for issue in issues
            if issue.get("type") == "missing_metric"
        }
        self.assertNotIn("1y_return_percent", missing_fields)

    def test_checks_nested_financial_statement_values(self):
        evaluator = EvaluatorAgent(lambda _prompt: "{}")
        observations = {
            "company_info": {"marketCap": 2_000_000_000},
            "financials": {"Total Revenue": {"2025": 1_000_000}},
        }

        issues = evaluator.validate_observations(observations)

        self.assertIn("scale_mismatch", {issue["type"] for issue in issues})

    def test_reflection_normalizes_model_output_and_retains_issues(self):
        response = json.dumps(
            {
                "strengths": ["Current price evidence"],
                "weaknesses": "wrong shape",
                "missing_information": [],
                "suspicious_values": [],
                "follow_up_questions": ["Can filing data be added?"],
            }
        )
        evaluator = EvaluatorAgent(lambda _prompt: response)
        issues = [{"type": "tool_error", "message": "News unavailable"}]

        reflection = evaluator.reflect(
            "AAPL",
            {"objectives": [], "tools": [], "questions": []},
            {},
            issues,
        )

        self.assertEqual(reflection["weaknesses"], ["News unavailable"])
        self.assertEqual(
            reflection["follow_up_questions"],
            ["Can filing data be added?"],
        )
        self.assertEqual(reflection["deterministic_issues"], issues)

    def test_report_validation_catches_false_cash_claim_and_advice(self):
        evaluator = EvaluatorAgent(lambda _prompt: "{}")
        observations = {
            "cash_flow": {"Free Cash Flow": {"2025": 100.0}},
        }

        issues = evaluator.validate_report(
            "Cash flow data is missing, so you should buy the stock.",
            observations,
        )

        self.assertEqual(
            {issue["type"] for issue in issues},
            {
                "false_missing_claim",
                "unsafe_language",
                "financial_mismatch",
                "missing_required_content",
            },
        )

    def test_report_rejects_incomplete_disclaimer_and_low_reasoning(self):
        evaluator = EvaluatorAgent(lambda _prompt: "{}")
        observations = {"price_data": {"latest_price": 110.0}}

        result = evaluator.evaluate_report(
            (
                "# Market report\n\nLatest price: 110. Source: Yahoo. "
                "This may not be comprehensive."
            ),
            observations,
            "Analyze the market",
            "market",
        )

        self.assertFalse(result["passed"])
        self.assertLess(result["criteria"]["reasoning"], 60)
        self.assertIn(
            "incomplete_report_claim",
            {issue["type"] for issue in result["validation_issues"]},
        )

    def test_setext_headings_count_toward_clarity(self):
        evaluator = EvaluatorAgent(lambda _prompt: "{}")
        report = """Market Analysis
===============

Price Evidence
--------------

The latest price is $110.00 according to a Yahoo source. The one-year return
is 10.00%. This evidence suggests momentum because the price increased;
however, historical performance creates uncertainty and risk. The observation
does not guarantee future results, therefore the source period should be
verified before drawing a conclusion about the market.
"""

        result = evaluator.evaluate_report(
            report,
            {"price_data": {"latest_price": 110, "1y_return_percent": 10}},
            "Analyze the market",
            "market",
        )

        self.assertEqual(result["criteria"]["clarity"], 50)

    def test_request_coverage_does_not_require_verbatim_repetition(self):
        evaluator = EvaluatorAgent(lambda _prompt: "{}")
        result = evaluator.evaluate_report(
            (
                "# Risk picture\n\nMarket performance, financial condition, SEC "
                "evidence, and recent news are evaluated for risk and uncertainty."
            ),
            {},
            (
                "How do market performance, financial condition, SEC evidence, "
                "and recent news affect the company's current risk picture?"
            ),
            "comprehensive",
        )

        self.assertNotIn(
            "Answer the user's research request explicitly.",
            result["feedback"],
        )

    def test_report_numerical_mismatch_caps_grounding_and_consistency(self):
        evaluator = EvaluatorAgent(lambda _prompt: "{}")
        observations = {
            "cash_flow": {"Free Cash Flow": {"2025": 98_767_000_000}}
        }

        result = evaluator.evaluate_report(
            "# Financial report\n\nFree Cash Flow: $987,670,000. Source evidence.",
            observations,
            "Analyze cash flow",
            "financial",
        )

        self.assertFalse(result["passed"])
        self.assertLessEqual(result["criteria"]["grounding"], 20)
        self.assertEqual(result["criteria"]["consistency"], 0)

    def test_report_validation_detects_rescaled_market_values(self):
        evaluator = EvaluatorAgent(lambda _prompt: "{}")
        observations = {
            "company_info": {
                "marketCap": 5_012_516_765_696,
                "returnOnEquity": 1.4875101,
            },
            "price_data": {"latest_volume": 59_852_690},
        }

        issues = evaluator.validate_report(
            (
                "Market Capitalization: $50,125,167,569; "
                "Return on Equity: 14.88%; Latest Volume: 598,526,900"
            ),
            observations,
        )

        messages = {
            issue["message"]
            for issue in issues
            if issue["type"] == "financial_mismatch"
        }
        self.assertIn(
            "Market Capitalization must be reported as $5,012,516,765,696.",
            messages,
        )
        self.assertIn("Return on Equity must be reported as 148.75%.", messages)
        self.assertIn("Latest Volume must be reported as 59,852,690.", messages)

    def test_report_validation_detects_changed_financial_digits(self):
        evaluator = EvaluatorAgent(lambda _prompt: "{}")
        observations = {
            "cash_flow": {
                "Free Cash Flow": {"2025": 98_767_000_000},
                "Capital Expenditure": {"2025": -12_715_000_000},
            }
        }

        issues = evaluator.validate_report(
            "Free Cash Flow: $987,670,000; Capital Expenditure: -$127B",
            observations,
        )

        messages = [
            issue["message"]
            for issue in issues
            if issue["type"] == "financial_mismatch"
        ]
        self.assertIn(
            "Free Cash Flow must be reported as $98,767,000,000.",
            messages,
        )
        self.assertIn(
            "Capital Expenditure must be reported as -$12,715,000,000.",
            messages,
        )


if __name__ == "__main__":
    unittest.main()
