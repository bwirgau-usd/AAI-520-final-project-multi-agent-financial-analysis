"""NewsAPI data-source adapter package."""

from .client import NewsApiClient, NewsApiError, fetch_company_articles

__all__ = ["NewsApiClient", "NewsApiError", "fetch_company_articles"]
