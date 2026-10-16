"""Provider-independent retrieval and prompt-chain operations for news."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlparse

from src.data_sources.base import NewsArticle
from src.data_sources.news_api.client import (
    NewsApiError,
    fetch_company_articles,
)

EARNINGS_KEYWORDS = (
    "earnings",
    "revenue",
    "eps",
    "profit",
    "quarter",
    "guidance",
    "financial results",
    "net income",
    "forecast",
)
MARKET_KEYWORDS = (
    "stock",
    "shares",
    "market",
    "price",
    "analyst",
    "valuation",
    "upgrade",
    "downgrade",
    "trading",
)
GENERAL_NEWS_KEYWORDS = (
    "acquisition",
    "merger",
    "lawsuit",
    "partnership",
    "product",
    "launch",
    "management",
    "investigation",
    "regulation",
)
EVENT_KEYWORDS = (
    "earnings",
    "acquisition",
    "merger",
    "layoffs",
    "product launch",
    "guidance",
    "partnership",
    "lawsuit",
    "dividend",
    "buyback",
    "investigation",
    "regulation",
)
EXTRACTION_KEYWORDS = (
    "revenue",
    "earnings",
    "eps",
    "profit",
    "growth",
    "guidance",
    "analyst",
    "market",
    "shares",
    "stock",
    "AI",
    "cloud",
    "acquisition",
    "dividend",
)
FINANCIAL_PATTERNS = (
    r"\$\d+(?:\.\d+)?(?:\s?(?:billion|million|trillion|B|M|T))?",
    r"\d+(?:\.\d+)?%",
    r"\d+(?:\.\d+)?\s?(?:million|billion|trillion)",
)


class YahooNewsClient(Protocol):
    """Yahoo news operation used by ingestion."""

    def get_news(
        self,
        symbol: str,
        max_articles: int = 8,
    ) -> list[NewsArticle]:
        """Return normalized Yahoo Finance articles."""


class NewsApiDataClient(Protocol):
    """NewsAPI operation used by ingestion."""

    def get_articles(
        self,
        symbol: str,
        max_articles: int = 8,
    ) -> list[NewsArticle]:
        """Return normalized NewsAPI articles."""


class GoogleNewsDataClient(Protocol):
    """Google News RSS operation used as a sparse-results fallback."""

    def get_articles(
        self,
        symbol: str,
        max_articles: int = 8,
    ) -> list[NewsArticle]:
        """Return normalized Google News RSS articles."""


def ingest_news(
    yahoo_client: YahooNewsClient,
    news_api_client: NewsApiDataClient,
    symbol: str,
    *,
    google_news_client: GoogleNewsDataClient | None = None,
    max_articles: int = 8,
) -> dict[str, Any]:
    """Retrieve primary sources and activate RSS when coverage is sparse."""

    source_errors: dict[str, str] = {}
    source_limit = min(max(1, int(max_articles)), 8)
    try:
        yahoo_articles = yahoo_client.get_news(symbol, source_limit)
    except Exception as exc:  # noqa: BLE001 - provider isolation boundary
        yahoo_articles = []
        source_errors["Yahoo Finance"] = f"{type(exc).__name__}: {exc}"

    try:
        news_api_articles = news_api_client.get_articles(symbol, source_limit)
    except Exception as exc:  # noqa: BLE001 - provider isolation boundary
        news_api_articles = []
        source_errors["NewsAPI"] = f"{type(exc).__name__}: {exc}"

    google_articles: list[NewsArticle] = []
    needs_fallback = not yahoo_articles and not news_api_articles
    sparse_yahoo = len(yahoo_articles) < 3
    if google_news_client is not None and (needs_fallback or sparse_yahoo):
        try:
            google_articles = google_news_client.get_articles(
                symbol,
                source_limit,
            )
        except Exception as exc:  # noqa: BLE001 - provider isolation boundary
            source_errors["Google News RSS"] = f"{type(exc).__name__}: {exc}"

    articles = combine_news_sources(
        yahoo_articles,
        news_api_articles,
        google_articles,
        max_articles=max_articles,
    )
    return {
        "articles": articles,
        "source_errors": source_errors,
        "retrieved_counts": {
            "Yahoo Finance": len(yahoo_articles),
            "NewsAPI": len(news_api_articles),
            "Google News RSS": len(google_articles),
        },
    }


def combine_news_sources(
    yahoo_articles: Sequence[NewsArticle],
    news_api_articles: Sequence[NewsArticle],
    google_articles: Sequence[NewsArticle] = (),
    *,
    max_articles: int = 8,
) -> list[NewsArticle]:
    """Deduplicate, newest-sort, and limit normalized provider articles."""

    combined: list[NewsArticle] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    for source_articles in (
        yahoo_articles,
        news_api_articles,
        google_articles,
    ):
        for article in source_articles:
            url_key = normalize_article_url(article.get("url"))
            title_key = normalize_title(article.get("title"))
            if url_key and url_key in seen_urls:
                continue
            if title_key and title_key in seen_titles:
                continue
            if url_key:
                seen_urls.add(url_key)
            if title_key:
                seen_titles.add(title_key)
            combined.append(dict(article))

    combined.sort(
        key=lambda article: str(article.get("published_at") or ""),
        reverse=True,
    )
    return combined[: max(0, int(max_articles))]


def preprocess_article(article: Mapping[str, Any]) -> NewsArticle:
    """Combine and normalize the article text used by later stages."""

    result: NewsArticle = dict(article)
    raw_text = normalize_text(
        " ".join(
            str(article.get(field) or "")
            for field in ("title", "summary", "description", "content")
        )
    )
    result["raw_text"] = raw_text
    result["normalized_text"] = raw_text.lower()
    return result


def classify_article(article: Mapping[str, Any]) -> NewsArticle:
    """Classify an article into earnings, market, or general news."""

    text = str(article.get("normalized_text") or "")
    scores = {
        "earnings": sum(keyword in text for keyword in EARNINGS_KEYWORDS),
        "market": sum(keyword in text for keyword in MARKET_KEYWORDS),
        "news": sum(keyword in text for keyword in GENERAL_NEWS_KEYWORDS),
    }
    category = max(scores, key=scores.__getitem__)
    if scores[category] == 0:
        category = "news"

    result: NewsArticle = dict(article)
    result["category"] = category
    result["classification_scores"] = scores
    return result


def extract_information(article: Mapping[str, Any]) -> NewsArticle:
    """Extract financial figures, events, and domain keywords."""

    text = str(article.get("raw_text") or "")
    lower_text = text.lower()
    financial_numbers: list[str] = []
    for pattern in FINANCIAL_PATTERNS:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if match not in financial_numbers:
                financial_numbers.append(match)

    extracted = {
        "financial_numbers": financial_numbers,
        "events": [event for event in EVENT_KEYWORDS if event in lower_text],
        "keywords": [
            keyword for keyword in EXTRACTION_KEYWORDS if keyword.lower() in lower_text
        ],
    }
    result: NewsArticle = dict(article)
    result["extracted"] = extracted
    return result


def summarize_article(article: Mapping[str, Any]) -> NewsArticle:
    """Create the structured summary passed into specialist routing."""

    extracted = article.get("extracted")
    fields = extracted if isinstance(extracted, Mapping) else {}
    result: NewsArticle = dict(article)
    result["summary_output"] = {
        "article_type": str(article.get("category") or "news"),
        "headline": str(article.get("title") or "Unknown title"),
        "detected_events": _joined(fields.get("events")),
        "financial_figures": _joined(fields.get("financial_numbers")),
        "keywords": _joined(fields.get("keywords")),
        "source": str(article.get("source") or "Unknown"),
    }
    return result


def normalize_text(text: object) -> str:
    """Collapse repeated whitespace in provider text."""

    return re.sub(r"\s+", " ", str(text or "")).strip()


def normalize_title(title: object) -> str:
    """Normalize a headline for duplicate detection."""

    text = re.sub(r"[^a-z0-9\s]", "", str(title or "").lower())
    return normalize_text(text)


def normalize_article_url(url: object) -> str:
    """Remove query parameters and fragments for duplicate detection."""

    if not url or url == "N/A":
        return ""
    parsed = urlparse(str(url))
    if not parsed.scheme or not parsed.netloc:
        return str(url).lower().strip().rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".lower().rstrip("/")


def get_company_news(
    symbol: str,
    company_name: str | None = None,
    max_articles: int = 10,
) -> list[dict[str, Any]]:
    """Compatibility facade retained from the merged NewsAPI pull request.

    The full research workflow uses the multi-source ``NewsPipeline``. This
    facade keeps the original symbol-only tool contract available to callers.
    """

    query = company_name or symbol
    try:
        raw_articles = fetch_company_articles(query, page_size=max_articles)
    except NewsApiError:
        return []

    seen_urls: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for raw_article in raw_articles:
        article = _normalize_compatibility_article(raw_article)
        if article is None or article["url"] in seen_urls:
            continue
        seen_urls.add(article["url"])
        normalized.append(article)
    normalized.sort(key=lambda article: article["date"] or "", reverse=True)
    return normalized[: max(0, int(max_articles))]


def articles_retrieved_at(_articles: Sequence[Mapping[str, Any]]) -> str:
    """Return a UTC retrieval timestamp for report traceability."""

    return datetime.now(timezone.utc).isoformat()


def _normalize_compatibility_article(
    raw_article: Mapping[str, Any],
) -> dict[str, Any] | None:
    title = str(raw_article.get("title") or "").strip()
    url = str(raw_article.get("url") or "").strip()
    if not title or not url:
        return None

    raw_source = raw_article.get("source")
    provider_source = (
        raw_source.get("name") if isinstance(raw_source, Mapping) else None
    )
    publisher = str(
        raw_article.get("publisher") or provider_source or "Unknown"
    ).strip()
    date = raw_article.get("publishedAt") or raw_article.get("published_at")
    text = str(
        raw_article.get("text")
        or raw_article.get("content")
        or raw_article.get("description")
        or raw_article.get("summary")
        or ""
    ).strip()
    return {
        "title": title,
        "publisher": publisher,
        "date": str(date) if date else None,
        "url": url,
        "text": text,
    }


def _joined(value: object) -> str:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return "none detected"
    values = [str(item) for item in value if str(item)]
    return ", ".join(values) or "none detected"
