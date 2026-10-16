"""Offline tests for the Google News RSS fallback adapter."""

from src.data_sources.google_news import GoogleNewsClient
from src.tools.news_tools import ingest_news

RSS = b"""<?xml version="1.0"?>
<rss><channel><item>
<title>Example &amp;amp; Co reports earnings</title>
<link>https://example.com/story</link>
<description>&lt;p&gt;Revenue rose 10%.&lt;/p&gt;</description>
<pubDate>Wed, 14 Oct 2026 12:00:00 GMT</pubDate>
<source>Example Publisher</source>
</item></channel></rss>
"""


class FakeResponse:
    status_code = 200
    content = RSS

    def raise_for_status(self):
        return None


class FakeGet:
    def __init__(self):
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()


class EmptyYahoo:
    def get_news(self, symbol, max_articles=8):
        return []


class EmptyNewsApi:
    def get_articles(self, symbol, max_articles=8):
        return []


def test_google_news_normalizes_rss_records():
    http_get = FakeGet()
    client = GoogleNewsClient(
        http_get=http_get,
        company_name_resolver=lambda _symbol: "Example Company",
    )

    articles = client.get_articles(" ex ")

    assert articles[0]["source"] == "Google News RSS"
    assert articles[0]["publisher"] == "Example Publisher"
    assert articles[0]["summary"] == "Revenue rose 10%."
    assert articles[0]["published_at"] == "2026-10-14T12:00:00+00:00"
    assert http_get.calls[0][1]["params"]["q"] == '"EX" "Example Company"'


def test_ingestion_activates_rss_when_primary_sources_are_empty():
    client = GoogleNewsClient(http_get=FakeGet())

    result = ingest_news(
        EmptyYahoo(),
        EmptyNewsApi(),
        "AAPL",
        google_news_client=client,
    )

    assert len(result["articles"]) == 1
    assert result["retrieved_counts"]["Google News RSS"] == 1
