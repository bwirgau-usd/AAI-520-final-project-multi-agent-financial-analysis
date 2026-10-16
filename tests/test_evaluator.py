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
            {"false_missing_claim", "unsafe_language"},
        )


if __name__ == "__main__":
    unittest.main()
