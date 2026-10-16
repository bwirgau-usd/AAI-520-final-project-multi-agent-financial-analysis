"""Offline tests for the NewsAPI adapter."""

import unittest
from unittest.mock import patch

from src.data_sources.news_api.client import NEWS_API_URL, NewsApiClient


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeGet:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class TestNewsApiClient(unittest.TestCase):
    def test_normalizes_articles_and_request_parameters(self):
        http_get = FakeGet(
            FakeResponse(
                {
                    "status": "ok",
                    "articles": [
                        {
                            "title": "Apple reports earnings",
                            "description": "Revenue increased.",
                            "content": "Quarterly details.",
                            "source": {"name": "Example News"},
                            "url": "https://example.com/apple",
                            "publishedAt": "2026-10-01T12:00:00Z",
                            "author": "Reporter",
                        }
                    ],
                }
            )
        )
        client = NewsApiClient(api_key="secret", http_get=http_get)

        result = client.get_articles(" aapl ", 500)

        self.assertEqual(result[0]["source"], "NewsAPI")
        self.assertEqual(result[0]["publisher"], "Example News")
        self.assertEqual(result[0]["summary"], "Revenue increased.")
        url, options = http_get.calls[0]
        self.assertEqual(url, NEWS_API_URL)
        self.assertIn('"AAPL stock"', options["params"]["q"])
        self.assertEqual(options["params"]["pageSize"], 100)
        self.assertEqual(options["params"]["apiKey"], "secret")
        self.assertEqual(options["timeout"], 30)

    def test_skips_optional_provider_when_key_is_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            result = NewsApiClient().get_articles("MSFT")

        self.assertEqual(result, [])

    def test_raises_descriptive_provider_error(self):
        client = NewsApiClient(
            api_key="secret",
            http_get=FakeGet(
                FakeResponse(
                    {"status": "error", "message": "rate limited"},
                    status_code=429,
                )
            ),
        )

        with self.assertRaisesRegex(RuntimeError, "rate limited"):
            client.get_articles("MSFT")

    def test_rejects_invalid_input_and_payload(self):
        client = NewsApiClient(api_key="secret", http_get=FakeGet(FakeResponse([])))

        with self.assertRaisesRegex(ValueError, "non-empty"):
            client.get_articles(" ")
        with self.assertRaisesRegex(TypeError, "non-object"):
            client.get_articles("AAPL")


if __name__ == "__main__":
    unittest.main()
