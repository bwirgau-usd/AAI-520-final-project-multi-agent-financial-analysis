"""NewsAPI ingestion adapter."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from src.data_sources.base import NewsArticle

NEWS_API_URL = "https://newsapi.org/v2/everything"


class NewsApiError(RuntimeError):
    """Raised when NewsAPI cannot return a usable response."""


class HttpResponse(Protocol):
    """Subset of an HTTP response used by the adapter."""

    status_code: int

    def json(self) -> Any:
        """Decode the response body."""


HttpGet = Callable[..., HttpResponse]
CompanyNameResolver = Callable[[str], str | None]


class NewsApiClient:
    """Retrieve and normalize company articles from NewsAPI."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        http_get: HttpGet | None = None,
        company_name_resolver: CompanyNameResolver | None = None,
        timeout: float = 30,
    ) -> None:
        self._api_key = api_key.strip() if api_key is not None else None
        self._http_get = http_get
        self._company_name_resolver = company_name_resolver
        self._timeout = timeout
        self._session: Any | None = None

    def get_articles(
        self,
        symbol: str,
        max_articles: int = 8,
        *,
        company_name: str | None = None,
        lookback_days: int | None = None,
    ) -> list[NewsArticle]:
        """Return newest English-language articles for a ticker."""

        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must be a non-empty string")

        api_key = (
            self._api_key
            if self._api_key is not None
            else os.getenv("NEWS_API_KEY", "").strip()
        )
        if not api_key:
            return []

        http_get = self._http_get or self._get_session().get

        page_size = max(1, min(int(max_articles), 100))
        resolved_name = company_name or self._resolve_company_name(normalized_symbol)
        query_parts = [
            f'"{normalized_symbol}"',
            f'"{normalized_symbol} stock"',
            f'"{normalized_symbol} shares"',
        ]
        if resolved_name and resolved_name.upper() != normalized_symbol:
            query_parts.extend([f'"{resolved_name}"', f'"{resolved_name} stock"'])
        params: dict[str, Any] = {
            "q": " OR ".join(query_parts),
            "apiKey": api_key,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": page_size,
        }
        if lookback_days is not None:
            params["from"] = (
                datetime.now(timezone.utc) - timedelta(days=max(0, int(lookback_days)))
            ).strftime("%Y-%m-%d")
        try:
            response = http_get(
                NEWS_API_URL,
                params=params,
                timeout=self._timeout,
            )
        except Exception as exc:
            category = classify_network_error(exc)
            raise NewsApiError(f"{category}: {type(exc).__name__}: {exc}") from exc

        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise NewsApiError("NewsAPI returned invalid JSON") from exc
        if not isinstance(payload, Mapping):
            raise TypeError("NewsAPI returned non-object JSON")
        if response.status_code != 200 or payload.get("status") != "ok":
            message = payload.get("message") or "Unknown NewsAPI error"
            raise NewsApiError(f"NewsAPI HTTP {response.status_code}: {message}")

        raw_articles = payload.get("articles", [])
        if not isinstance(raw_articles, Sequence) or isinstance(
            raw_articles, (str, bytes)
        ):
            return []

        articles: list[NewsArticle] = []
        for raw_item in raw_articles:
            if not isinstance(raw_item, Mapping):
                continue
            source = raw_item.get("source")
            source_name = source.get("name") if isinstance(source, Mapping) else None
            articles.append(
                {
                    "title": str(raw_item.get("title") or "Unknown title"),
                    "summary": str(raw_item.get("description") or ""),
                    "description": str(raw_item.get("description") or ""),
                    "content": str(raw_item.get("content") or ""),
                    "publisher": str(source_name or "Unknown"),
                    "url": str(raw_item.get("url") or "N/A"),
                    "published_at": _optional_text(raw_item.get("publishedAt")),
                    "author": _optional_text(raw_item.get("author")),
                    "source": "NewsAPI",
                }
            )
        return articles

    def _resolve_company_name(self, symbol: str) -> str | None:
        if self._company_name_resolver is None:
            return None
        try:
            return self._company_name_resolver(symbol)
        except Exception:  # noqa: BLE001 - company name is query enrichment
            return None

    def _get_session(self) -> Any:
        """Build one retry-enabled session for transient HTTP failures."""

        if self._session is not None:
            return self._session
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
        except ImportError as exc:  # pragma: no cover - dependency failure
            raise RuntimeError(
                "The requests package is required. Install project "
                "dependencies from requirements.txt."
            ) from exc

        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
        )
        session = requests.Session()
        session.headers.update({"User-Agent": "AAI-520-Financial-Research/1.0"})
        session.mount("https://", HTTPAdapter(max_retries=retry))
        session.mount("http://", HTTPAdapter(max_retries=retry))
        self._session = session
        return session


def classify_network_error(exc: Exception) -> str:
    """Return a concise category for a provider connection failure."""

    text = f"{type(exc).__name__}: {exc}".lower()
    if any(term in text for term in ("ssl", "certificate", "tls")):
        return "TLS/SSL connection problem"
    if "timeout" in text:
        return "Network timeout"
    if "connection" in text:
        return "Connection problem"
    return "Network problem"


def fetch_company_articles(
    company_name: str,
    lookback_days: int = 14,
    page_size: int = 20,
) -> list[dict[str, Any]]:
    """Compatibility entry point for the original NewsAPI tool.

    ``lookback_days`` is retained for callers from the merged pull request;
    the provider query is sorted by publication date and bounded by page size.
    """

    try:
        articles = NewsApiClient().get_articles(
            company_name,
            page_size,
            company_name=company_name,
            lookback_days=lookback_days,
        )
    except NewsApiError:
        raise
    except Exception as exc:
        raise NewsApiError(str(exc)) from exc
    return [dict(article) for article in articles]


def _optional_text(value: object) -> str | None:
    return str(value) if value not in (None, "") else None
