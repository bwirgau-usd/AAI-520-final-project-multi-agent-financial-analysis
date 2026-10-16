"""Route classified news to deterministic domain specialists."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from src.agents.financial_agent import analyze_earnings_article
from src.agents.market_agent import analyze_market_article
from src.agents.news_agent import analyze_general_news_article
from src.data_sources.base import NewsArticle

Specialist = Callable[[Mapping[str, Any]], dict[str, Any]]


class SpecialistRouter:
    """Map article categories to the matching specialist."""

    def __init__(self, specialists: Mapping[str, Specialist] | None = None) -> None:
        self._specialists = dict(
            specialists
            or {
                "earnings": analyze_earnings_article,
                "market": analyze_market_article,
                "news": analyze_general_news_article,
            }
        )

    def route(self, article: Mapping[str, Any]) -> NewsArticle:
        """Attach specialist identity and deterministic fallback analysis."""

        category = str(article.get("category") or "news")
        specialist = self._specialists.get(
            category,
            self._specialists.get("news", analyze_general_news_article),
        )
        analysis = specialist(article)
        result: NewsArticle = dict(article)
        result["specialist"] = str(analysis.get("specialist") or category)
        result["specialist_analysis"] = analysis
        return result
