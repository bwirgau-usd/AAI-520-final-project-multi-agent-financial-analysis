"""Offline end-to-end tests for the extracted news workflow."""

import json
import unittest

from src.workflows.news_pipeline import build_news_pipeline


class FakeYahooNews:
    def get_news(self, symbol, max_articles=8):
        return [
            {
                "title": f"{symbol} earnings and revenue update",
                "summary": "Revenue was $5 billion and earnings grew 10%.",
                "description": "Management also issued guidance.",
                "content": "",
                "publisher": "Example",
                "url": "https://example.com/earnings",
                "published_at": "2026-10-01T12:00:00Z",
                "author": None,
                "source": "Yahoo Finance",
            }
        ]


class EmptyNewsApi:
    def get_articles(self, symbol, max_articles=8):
        return []


class ImprovingLlm:
    def __init__(self):
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if "optimizing a financial-news analysis" in prompt:
            return json.dumps(
                {
                    "specialist": "earnings",
                    "observations": [
                        "Revenue was reported as $5 billion.",
                        "Earnings growth was reported as 10%.",
                    ],
                    "interpretation": "The article reports an earnings update.",
                    "uncertainties": ["No prior-period base was supplied."],
                    "improvements": ["Added interpretation and uncertainty."],
                }
            )
        return json.dumps(
            {
                "specialist": "earnings",
                "observations": [
                    "Revenue was reported as $5 billion.",
                    "Earnings growth was reported as 10%.",
                ],
                "interpretation": "",
                "uncertainties": [],
            }
        )


class TestNewsPipeline(unittest.TestCase):
    def test_runs_prompt_chain_routing_and_optimizer_loop(self):
        llm = ImprovingLlm()
        pipeline = build_news_pipeline(
            llm,
            yahoo_client=FakeYahooNews(),
            news_api_client=EmptyNewsApi(),
            evaluation_threshold=75,
            max_optimizer_iterations=2,
        )
        progress = []

        result = pipeline.analyze(" aapl ", progress=progress.append)

        self.assertEqual(result["ticker"], "AAPL")
        self.assertEqual(result["article_count"], 1)
        self.assertEqual(result["source_counts"], {"Yahoo Finance": 1})
        self.assertEqual(result["routing_counts"], {"earnings": 1})
        self.assertEqual(result["average_score"], 100)
        self.assertEqual(result["average_structural_score"], 100)
        self.assertEqual(result["average_substantive_reasoning_score"], 100)
        self.assertEqual(result["passed_count"], 1)
        article = result["articles"][0]
        self.assertEqual(article["category"], "earnings")
        self.assertEqual(article["specialist"], "earnings")
        self.assertEqual(
            [item["score"] for item in article["evaluation_history"]], [25, 100]
        )
        self.assertEqual(len(article["optimization_history"]), 1)
        self.assertIn(
            "Added interpretation", article["optimized_analysis"]["improvements"][0]
        )
        # Classification, extraction, and summarization are now part of the
        # production prompt chain, followed by specialist analysis/optimization.
        self.assertEqual(len(llm.prompts), 5)
        self.assertIn("classification_confidence", article)
        self.assertIn("sentiment", article["extracted"])
        self.assertEqual(progress, ["Processing news article 1/1"])

    def test_returns_complete_empty_summary_when_no_articles_exist(self):
        pipeline = build_news_pipeline(
            lambda _prompt: "{}",
            yahoo_client=type(
                "EmptyYahoo",
                (),
                {"get_news": lambda self, symbol, max_articles=8: []},
            )(),
            news_api_client=EmptyNewsApi(),
        )

        result = pipeline.analyze("MSFT")

        self.assertEqual(result["articles"], [])
        self.assertEqual(result["article_count"], 0)
        self.assertIsNone(result["average_score"])
        self.assertIsNone(result["average_structural_score"])
        self.assertIsNone(result["average_substantive_reasoning_score"])
        self.assertEqual(result["pipeline_stages"][-1], "optimize")


if __name__ == "__main__":
    unittest.main()
