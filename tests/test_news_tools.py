from unittest.mock import patch

from src.data_sources.news_api.client import NewsApiError
from src.tools.news_tools import get_company_news

RAW_ARTICLE = {
    "title": "Company beats earnings expectations",
    "url": "https://example.com/article-1",
    "content": "Full article text here.",
    "publishedAt": "2026-09-20T12:00:00Z",
    "source": {"name": "Example News"},
}


def test_get_company_news_normalizes_articles():
    with patch("src.tools.news_tools.fetch_company_articles", return_value=[RAW_ARTICLE]):
        articles = get_company_news("AAPL")

    assert len(articles) == 1
    assert articles[0]["title"] == RAW_ARTICLE["title"]
    assert articles[0]["publisher"] == "Example News"


def test_get_company_news_dedupes_by_url():
    with patch(
        "src.tools.news_tools.fetch_company_articles",
        return_value=[RAW_ARTICLE, RAW_ARTICLE],
    ):
        articles = get_company_news("AAPL")

    assert len(articles) == 1


def test_get_company_news_drops_articles_missing_title_or_url():
    incomplete = {**RAW_ARTICLE, "title": ""}
    with patch("src.tools.news_tools.fetch_company_articles", return_value=[incomplete]):
        articles = get_company_news("AAPL")

    assert articles == []


def test_get_company_news_returns_empty_list_on_provider_failure():
    with patch("src.tools.news_tools.fetch_company_articles", side_effect=NewsApiError("boom")):
        articles = get_company_news("AAPL")

    assert articles == []


def test_get_company_news_respects_max_articles():
    articles_in = [
        {**RAW_ARTICLE, "url": f"https://example.com/article-{i}"} for i in range(15)
    ]
    with patch("src.tools.news_tools.fetch_company_articles", return_value=articles_in):
        articles = get_company_news("AAPL", max_articles=5)

    assert len(articles) == 5
