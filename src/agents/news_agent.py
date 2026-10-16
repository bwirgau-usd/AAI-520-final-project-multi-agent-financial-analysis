"""General-news specialist and model-assisted specialist analysis."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from src.llm import parse_json_object
from src.tools.news_tools import articles_retrieved_at, get_company_news


class NewsAgent:
    """Turn routed article evidence into a grounded specialist analysis."""

    def __init__(self, llm: Callable[[str], str]) -> None:
        self._llm = llm

    def analyze(
        self,
        article: Mapping[str, Any],
        fallback: Mapping[str, Any],
        research_request: str = "",
    ) -> dict[str, Any]:
        """Ask the model for observations, interpretation, and uncertainty."""

        specialist = str(fallback.get("specialist") or "news")
        prompt = f"""
You are a {specialist} financial news analyst. Analyze only the supplied
article evidence.

User research request: {research_request or 'general company research'}

Article:
{json.dumps(article, default=str)}

Return only JSON with fields specialist, observations, interpretation, and
uncertainties.

Rules:
- Identify concrete factual observations and explain why they matter.
- Identify uncertainty or missing information.
- Do not invent facts or financial figures.
- Do not predict the stock price or recommend buy, sell, or hold.
""".strip()
        parsed = parse_json_object(self._llm(prompt), fallback=fallback)
        return {
            "specialist": specialist,
            "observations": _string_list(parsed.get("observations"))
            or _string_list(fallback.get("observations")),
            "interpretation": _string(parsed.get("interpretation")),
            "uncertainties": _string_list(parsed.get("uncertainties")),
            "focus": _string(parsed.get("focus")) or _string(fallback.get("focus")),
        }


def analyze_general_news_article(article: Mapping[str, Any]) -> dict[str, Any]:
    """Build a grounded fallback analysis for general company news."""

    extracted = _mapping(article.get("extracted"))
    return {
        "specialist": "news",
        "observations": [
            f"Events: {_joined(extracted.get('events'))}",
            f"Keywords: {_joined(extracted.get('keywords'))}",
        ],
        "interpretation": "",
        "uncertainties": [],
        "focus": "General company developments and material events.",
    }


def run_news_agent(
    symbol: str,
    company_name: str | None = None,
) -> dict[str, Any]:
    """Run the compatibility NewsAPI chain and preserve source metadata."""

    # Imported lazily because the production pipeline imports ``NewsAgent``.
    from src.workflows.news_pipeline import run_news_pipeline

    articles = get_company_news(symbol, company_name=company_name)
    pipeline_output = run_news_pipeline(symbol, articles)
    sources = [
        {
            "title": article["title"],
            "publisher": article["publisher"],
            "url": article["url"],
            "date": article["date"],
        }
        for article in pipeline_output["extracted"]
    ]
    return {
        "symbol": symbol.strip().upper(),
        "retrieved_at": articles_retrieved_at(articles),
        "article_count": len(articles),
        "summary": pipeline_output["summary"],
        "classified_articles": pipeline_output["classified"],
        "extracted_facts": pipeline_output["extracted"],
        "sources": sources,
    }


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _joined(value: object) -> str:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return "none"
    return ", ".join(str(item) for item in value) or "none"


def _string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
