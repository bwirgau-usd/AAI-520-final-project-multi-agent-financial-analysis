"""Tests for news specialist routing, evaluation, and optimization."""

import json
import unittest

from src.agents import NewsAgent, OptimizerAgent, SpecialistRouter
from src.agents.optimizer import evaluate_analysis

ARTICLE = {
    "title": "Example earnings",
    "raw_text": (
        "Example earnings. Revenue was $5 billion, up 10%, and earnings "
        "guidance was issued."
    ),
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
        self.assertTrue(earnings["specialist_analysis"]["observations"])
        self.assertNotIn(
            "none",
            " ".join(earnings["specialist_analysis"]["observations"]).lower(),
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
        self.assertEqual(result["observations"], ["Revenue was $5 billion."])
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

    def test_evaluator_rejects_placeholders_and_ungrounded_observations(self):
        result = evaluate_analysis(
            {
                "observations": ["Financial figures: null", "Profit doubled."],
                "interpretation": "N/A",
                "uncertainties": ["none"],
            },
            article=ARTICLE,
        )

        self.assertEqual(result["score"], 0)
        self.assertFalse(result["passed"])
        self.assertEqual(result["rejected_observations"], ["Profit doubled."])

    def test_structural_score_does_not_overstate_generic_headline_analysis(self):
        article = {
            "title": "Example announces an update",
            "source": "Example Wire",
            "published_at": "2026-10-01",
        }
        result = evaluate_analysis(
            {
                "observations": [
                    "Headline: Example announces an update",
                    "Source and date: Example Wire, 2026-10-01",
                ],
                "interpretation": (
                    "The supplied article provides evidence relevant to the "
                    "reported company development; its investment significance "
                    "requires corroboration with primary financial data."
                ),
                "uncertainties": ["Only headline metadata was supplied."],
            },
            article=article,
        )

        self.assertEqual(result["score"], 100)
        self.assertTrue(result["passed"])
        self.assertEqual(result["substantive_reasoning_score"], 0)
        self.assertFalse(result["substantive_reasoning_passed"])
        self.assertIn("Structural completeness passed", result["feedback"][-1])

    def test_optimizer_uses_feedback_and_preserves_grounding_fields(self):
        response = json.dumps(
            {
                "specialist": "earnings",
                "observations": [
                    "Revenue was $5 billion.",
                    "Earnings guidance was issued.",
                ],
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
        self.assertGreaterEqual(len(result["observations"]), 2)
        self.assertIn("Revenue was $5 billion.", result["observations"])

    def test_report_optimizer_adds_grounded_cross_domain_reasoning(self):
        optimizer = OptimizerAgent(lambda _prompt: "# Revised report")
        observations = {
            "price_data": {
                "1y_return_percent": 10.0,
                "annualized_volatility_percent": 20.0,
                "maximum_drawdown_percent": -15.0,
            },
            "balance_sheet": {"latest": {"cash": 80.0, "debt": 100.0}},
            "financial_growth": {
                "revenue_growth_percent": 5.0,
                "net_income_growth_percent": 4.0,
            },
            "sec_edgar": {
                "official_company_facts": {"Assets": {"value": 200.0}},
                "recent_filings": [{"form": "10-Q"}],
            },
            "news_analysis": {
                "article_count": 2,
                "average_score": 75.0,
                "average_structural_score": 75.0,
                "average_substantive_reasoning_score": 50.0,
            },
        }

        report = optimizer.optimize_report(
            "AAPL",
            "Assess current risk.",
            "# Draft",
            {"feedback": ["Add reasoning"]},
            observations,
            {},
        )

        self.assertIn("## Evidence-Based Interpretation", report)
        self.assertIn("Because the one-year return was 10.00%", report)
        self.assertIn("Cash of $80", report)
        self.assertIn("SEC EDGAR supplied 1 official company fact", report)
        self.assertIn("news workflow processed 2 article", report)
        self.assertIn("structural completeness", report)
        self.assertIn("substantive financial-reasoning", report)
        self.assertIn("does not establish perfect financial analysis", report)


if __name__ == "__main__":
    unittest.main()
