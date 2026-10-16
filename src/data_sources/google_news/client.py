"""Google News RSS adapter used when primary company-news sources are sparse."""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from typing import Any, Protocol
from xml.etree import ElementTree

from src.data_sources.base import NewsArticle

GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"


class HttpResponse(Protocol):
    """Subset of an HTTP response consumed by the RSS adapter."""

    status_code: int
    content: bytes

    def raise_for_status(self) -> None:
        """Raise when the response status is unsuccessful."""


HttpGet = Callable[..., HttpResponse]
CompanyNameResolver = Callable[[str], str | None]


class GoogleNewsClient:
    """Retrieve and normalize Google News RSS search results."""

    def __init__(
        self,
        *,
        http_get: HttpGet | None = None,
        company_name_resolver: CompanyNameResolver | None = None,
        timeout: float = 30,
    ) -> None:
        self._http_get = http_get
        self._company_name_resolver = company_name_resolver
        self._timeout = timeout
        self._session: Any | None = None

    def get_articles(
        self,
        symbol: str,
        max_articles: int = 8,
    ) -> list[NewsArticle]:
        """Return recent RSS articles for a ticker and resolved company name."""

        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must be a non-empty string")

        company_name = self._resolve_company_name(normalized_symbol)
        query = f'"{normalized_symbol}"'
        if company_name and company_name.upper() != normalized_symbol:
            query = f'{query} "{company_name}"'

        response = (self._http_get or self._get_session().get)(
            GOOGLE_NEWS_RSS_URL,
            params={
                "q": query,
                "hl": "en-US",
                "gl": "US",
                "ceid": "US:en",
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        channel = root.find("channel")
        if channel is None:
            return []

        articles: list[NewsArticle] = []
        limit = max(0, int(max_articles))
        for item in channel.findall("item")[:limit]:
            articles.append(
                {
                    "title": _clean_html(_node_text(item, "title")),
                    "summary": _clean_html(_node_text(item, "description")),
                    "description": _clean_html(_node_text(item, "description")),
                    "content": "",
                    "publisher": _node_text(item, "source") or "Google News",
                    "url": _node_text(item, "link") or "N/A",
                    "published_at": _parse_date(_node_text(item, "pubDate")),
                    "author": None,
                    "source": "Google News RSS",
                }
            )
        return articles

    def _resolve_company_name(self, symbol: str) -> str | None:
        if self._company_name_resolver is None:
            return None
        try:
            return self._company_name_resolver(symbol)
        except Exception:  # noqa: BLE001 - a name is optional for the fallback
            return None

    def _get_session(self) -> Any:
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


def _node_text(item: ElementTree.Element, name: str) -> str:
    node = item.find(name)
    return str(node.text or "").strip() if node is not None else ""


def _clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(value))).strip()


def _parse_date(value: str) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError, OverflowError):
        return value
