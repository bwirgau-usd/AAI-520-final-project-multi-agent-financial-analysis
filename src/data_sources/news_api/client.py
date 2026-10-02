"""NewsAPI ingestion adapter.

NewsAPI authentication, article retrieval, and response parsing belong in this
module.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from newsapi import NewsApiClient
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class NewsApiError(RuntimeError):
    """Raised when NewsAPI cannot return usable article data."""


def _get_client() -> NewsApiClient:
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        raise NewsApiError("NEWS_API_KEY is not set.")
    return NewsApiClient(api_key=api_key)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
)
def _fetch_everything(client: NewsApiClient, query: str, from_date: str, page_size: int) -> dict[str, Any]:
    return client.get_everything(
        qintitle=query,
        from_param=from_date,
        language="en",
        sort_by="publishedAt",
        page_size=page_size,
    )


def fetch_company_articles(
    company_name: str,
    lookback_days: int = 14,
    page_size: int = 20,
) -> list[dict[str, Any]]:
    """Fetch raw NewsAPI articles mentioning a company.

    Returns the provider's raw article records. Normalization into the
    project's article schema happens in ``src/tools/news_tools.py``.
    """
    client = _get_client()
    from_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    # Quote the phrase so NewsAPI requires an exact match instead of matching
    # any article that mentions the word anywhere (e.g. "apple" the fruit).
    query = f'"{company_name}"'

    try:
        response = _fetch_everything(client, query, from_date, page_size)
    except Exception as exc:  # NewsAPI raises plain exceptions/newsapi.NewsAPIException
        raise NewsApiError(f"NewsAPI request failed for '{company_name}': {exc}") from exc

    if response.get("status") != "ok":
        raise NewsApiError(f"NewsAPI returned an error status: {response.get('message', 'unknown error')}")

    return response.get("articles", [])
