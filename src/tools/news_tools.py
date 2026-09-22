"""Provider-independent tools for retrieving and preprocessing news.

These tools coordinate news-source adapters and normalize articles before they
enter the prompt-chaining workflow.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from src.data_sources.news_api.client import NewsApiError, fetch_company_articles


@dataclass
class NewsArticle:
    """A normalized, provider-independent news record."""

    title: str
    publisher: str
    date: str | None
    url: str
    text: str


def _normalize(raw_article: dict[str, Any]) -> NewsArticle | None:
    title = (raw_article.get("title") or "").strip()
    url = (raw_article.get("url") or "").strip()
    text = (raw_article.get("content") or raw_article.get("description") or "").strip()

    if not title or not url:
        return None

    source = raw_article.get("source") or {}
    publisher = (source.get("name") or "Unknown").strip()
    published_at = raw_article.get("publishedAt")

    return NewsArticle(title=title, publisher=publisher, date=published_at, url=url, text=text)


def get_company_news(
    symbol: str,
    company_name: str | None = None,
    max_articles: int = 10,
) -> list[dict[str, Any]]:
    """Retrieve deduplicated, normalized news articles for a company.

    Falls back to an empty list (rather than raising) when the provider is
    unavailable or misconfigured, so the calling agent can decide how to
    proceed without crashing the workflow.
    """
    query = company_name or symbol

    try:
        raw_articles = fetch_company_articles(query)
    except NewsApiError:
        return []

    seen_urls: set[str] = set()
    articles: list[NewsArticle] = []

    for raw_article in raw_articles:
        article = _normalize(raw_article)
        if article is None or article.url in seen_urls:
            continue
        seen_urls.add(article.url)
        articles.append(article)

    articles.sort(key=lambda a: a.date or "", reverse=True)

    return [asdict(a) for a in articles[:max_articles]]


def articles_retrieved_at(articles: list[dict[str, Any]]) -> str:
    """Attach a retrieval timestamp for source traceability in the report."""
    return datetime.now(timezone.utc).isoformat()
