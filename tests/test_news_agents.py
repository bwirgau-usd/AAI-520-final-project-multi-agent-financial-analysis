"""Tests for news specialist routing, evaluation, and optimization."""

import json
import unittest

from src.agents import NewsAgent, OptimizerAgent, SpecialistRouter
from src.agents.optimizer import evaluate_analysis

ARTICLE = {
    "title": "Example earnings",
    "category": "earnings",
    "extracted": {
        "financial_numbers": ["$5 billion", "10%"],
        "events": ["earnings", "guidance"],
        "keywords": ["revenue", "eps"],
    },
}


class TestNewsAgents(unittest.TestCase):
    def test_routes_each_category_to_its_specialist(self):
        router = SpecialistRouter()

        earnings = router.route(ARTICLE)
        market = router.route({**ARTICLE, "category": "market"})
        news = router.route({**ARTICLE, "category": "unknown"})

        self.assertEqual(earnings["specialist"], "earnings")
        self.assertIn(
            "Financial figures", earnings["specialist_analysis"]["observations"][0]
        )
        self.assertEqual(market["specialist"], "market")
        self.assertEqual(news["specialist"], "news")

    def test_model_specialist_analysis_is_normalized(self):
        response = json.dumps(
            {
                "specialist": "wrong-specialist",
                "observations": ["Revenue was $5 billion.", "Guidance changed."],
                "interpretation": "The supplied figures describe earnings.",
                "uncertainties": ["No prior-period comparison was supplied."],
            }
        )
        fallback = SpecialistRouter().route(ARTICLE)["specialist_analysis"]

        result = NewsAgent(lambda _prompt: response).analyze(ARTICLE, fallback)

        self.assertEqual(result["specialist"], "earnings")
        self.assertEqual(len(result["observations"]), 2)
        self.assertIn("comparison", result["uncertainties"][0])

    def test_evaluator_uses_four_25_point_criteria(self):
        weak = evaluate_analysis(
            {"observations": ["One fact"], "interpretation": "", "uncertainties": []}
        )
        strong = evaluate_analysis(
            {
                "observations": ["Fact one", "Fact two"],
                "interpretation": "Context",
                "uncertainties": ["Unknown timing"],
            }
        )

        self.assertEqual(weak["score"], 25)
        self.assertFalse(weak["passed"])
        self.assertEqual(strong["score"], 100)
        self.assertTrue(strong["passed"])

    def test_optimizer_uses_feedback_and_preserves_grounding_fields(self):
        response = json.dumps(
            {
                "specialist": "earnings",
                "observations": ["Fact one", "Fact two"],
                "interpretation": "Clearer context",
                "uncertainties": ["Missing comparison"],
                "improvements": ["Added context"],
            }
        )
        result = OptimizerAgent(lambda _prompt: response).optimize(
            ARTICLE,
            {"specialist": "earnings", "observations": ["Fact one"]},
            {"feedback": ["Add another observation"]},
        )

        self.assertEqual(result["interpretation"], "Clearer context")
        self.assertEqual(result["improvements"], ["Added context"])
        self.assertEqual(len(result["observations"]), 2)


if __name__ == "__main__":
    unittest.main()
