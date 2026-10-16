"""Tests for deterministic news ingestion and prompt-chain operations."""

import unittest

from src.tools.news_tools import (
    classify_article,
    combine_news_sources,
    extract_information,
    ingest_news,
    normalize_article_url,
    normalize_title,
    preprocess_article,
    summarize_article,
)


class FakeYahooClient:
    def get_news(self, symbol, max_articles=8):
        return [
            {
                "title": "Apple Earnings Rise!",
                "summary": "Revenue reached $12.5 billion, up 10%.",
                "description": "Guidance was discussed.",
                "content": "",
                "publisher": "Yahoo Publisher",
                "url": "https://example.com/story?source=yahoo",
                "published_at": "2026-10-02T12:00:00Z",
                "author": None,
                "source": "Yahoo Finance",
            }
        ]


class FakeNewsApiClient:
    def get_articles(self, symbol, max_articles=8):
        return [
            {
                "title": "Apple Earnings Rise",
                "summary": "Duplicate",
                "description": "",
                "content": "",
                "publisher": "API Publisher",
                "url": "https://example.com/story#section",
                "published_at": "2026-10-01T12:00:00Z",
                "author": None,
                "source": "NewsAPI",
            },
            {
                "title": "Apple launches product",
                "summary": "A product launch and partnership were announced.",
                "description": "",
                "content": "",
                "publisher": "API Publisher",
                "url": "https://example.com/product",
                "published_at": "2026-10-03T12:00:00Z",
                "author": None,
                "source": "NewsAPI",
            },
        ]


class FailingNewsApiClient:
    def get_articles(self, symbol, max_articles=8):
        raise RuntimeError("provider unavailable")


class TestNewsTools(unittest.TestCase):
    def test_combines_deduplicates_sorts_and_limits_sources(self):
        result = ingest_news(
            FakeYahooClient(),
            FakeNewsApiClient(),
            "AAPL",
            max_articles=2,
        )

        self.assertEqual(len(result["articles"]), 2)
        self.assertEqual(result["articles"][0]["title"], "Apple launches product")
        self.assertEqual(result["retrieved_counts"]["Yahoo Finance"], 1)
        self.assertEqual(result["retrieved_counts"]["NewsAPI"], 2)
        self.assertEqual(result["source_errors"], {})

    def test_isolates_provider_failure(self):
        result = ingest_news(
            FakeYahooClient(),
            FailingNewsApiClient(),
            "AAPL",
        )

        self.assertEqual(len(result["articles"]), 1)
        self.assertIn("provider unavailable", result["source_errors"]["NewsAPI"])

    def test_runs_preprocess_classify_extract_summarize_chain(self):
        article = FakeYahooClient().get_news("AAPL")[0]

        article = preprocess_article(article)
        article = classify_article(article)
        article = extract_information(article)
        article = summarize_article(article)

        self.assertIn("apple earnings rise", article["normalized_text"])
        self.assertEqual(article["category"], "earnings")
        self.assertIn("$12.5 billion", article["extracted"]["financial_numbers"])
        self.assertIn("10%", article["extracted"]["financial_numbers"])
        self.assertIn("guidance", article["extracted"]["events"])
        self.assertEqual(article["summary_output"]["article_type"], "earnings")
        self.assertEqual(article["summary_output"]["source"], "Yahoo Finance")

    def test_normalizers_match_titles_and_urls_without_tracking_data(self):
        self.assertEqual(normalize_title("Apple: Earnings!"), "apple earnings")
        self.assertEqual(
            normalize_article_url("HTTPS://Example.com/story?a=1#section"),
            "https://example.com/story",
        )

    def test_combiner_honors_zero_limit(self):
        self.assertEqual(
            combine_news_sources(
                FakeYahooClient().get_news("AAPL"),
                [],
                max_articles=0,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
