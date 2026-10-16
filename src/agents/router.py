"""Route research requests and classified news to domain specialists."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from typing import Any, ClassVar

from src.agents.financial_agent import analyze_earnings_article
from src.agents.market_agent import analyze_market_article
from src.agents.news_agent import analyze_general_news_article
from src.data_sources.base import NewsArticle

Specialist = Callable[[Mapping[str, Any]], dict[str, Any]]

MARKET_TOOLS = ("price_data", "company_info")
FINANCIAL_TOOLS = (
    "company_info",
    "financials",
    "cash_flow",
    "balance_sheet",
    "financial_growth",
    "sec_edgar",
)


class ResearchRequestRouter:
    """Choose a bounded specialist path from a user's research question."""

    _MARKET_TERMS: ClassVar[frozenset[str]] = frozenset({
        "price",
        "return",
        "volatility",
        "drawdown",
        "volume",
        "technical",
        "market",
        "stock performance",
    })
    _FINANCIAL_TERMS: ClassVar[frozenset[str]] = frozenset({
        "financial",
        "fundamental",
        "revenue",
        "earnings",
        "income",
        "cash flow",
        "balance sheet",
        "debt",
        "sec",
        "filing",
    })
    _NEWS_TERMS: ClassVar[frozenset[str]] = frozenset({
        "news",
        "headline",
        "catalyst",
        "event",
        "sentiment",
        "announcement",
    })

    def route(
        self,
        request: str,
        available_tools: Collection[str],
        *,
        has_news_pipeline: bool,
    ) -> dict[str, Any]:
        """Return route, specialists, and allowed tools for one request."""

        normalized = request.lower()
        matches = {
            "market": any(term in normalized for term in self._MARKET_TERMS),
            "financial": any(term in normalized for term in self._FINANCIAL_TERMS),
            "news": any(term in normalized for term in self._NEWS_TERMS),
        }
        selected = [name for name, matched in matches.items() if matched]
        if len(selected) != 1:
            route = "comprehensive"
            specialists = ["market", "financial"]
            if has_news_pipeline:
                specialists.append("news")
            candidate_tools = (*MARKET_TOOLS, *FINANCIAL_TOOLS)
        else:
            route = selected[0]
            specialists = [route]
            if route == "market":
                candidate_tools = MARKET_TOOLS
            elif route == "financial":
                candidate_tools = FINANCIAL_TOOLS
            else:
                candidate_tools = ()

        registered = set(available_tools)
        return {
            "route": route,
            "specialists": specialists,
            "tools": [name for name in dict.fromkeys(candidate_tools) if name in registered],
        }


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
