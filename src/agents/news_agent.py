"""General-news specialist and model-assisted specialist analysis."""

from __future__ import annotations

import json
from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Any

from src.agents.analysis_quality import (
    evidence_based_fallback,
    grounded_observations,
    meaningful_text,
    meaningful_text_list,
)
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
        planning_actions: Collection[str] = (),
    ) -> dict[str, Any]:
        """Ask the model for observations, interpretation, and uncertainty."""

        specialist = str(fallback.get("specialist") or "news")
        prompt = f"""
You are a {specialist} financial news analyst. Analyze only the supplied
article evidence.

User research request: {research_request or 'general company research'}

Saved next-run actions that this analysis must apply:
{json.dumps(list(planning_actions), default=str)}

Article:
{json.dumps(article, default=str)}

Return only JSON with fields specialist, observations, interpretation, and
uncertainties.

Rules:
- Identify concrete factual observations and explain why they matter.
- Explain the financial transmission mechanism using article evidence: how a
  material event could affect revenue, costs, cash flow, risk, or valuation.
- If the supplied article does not establish a material financial effect, say
  so explicitly instead of inventing significance.
- Identify uncertainty or missing information.
- Do not invent facts or financial figures.
- Do not predict the stock price or recommend buy, sell, or hold.
""".strip()
        parsed = parse_json_object(self._llm(prompt), fallback={})
        proposed = meaningful_text_list(parsed.get("observations"))
        observations, _ = grounded_observations(proposed, article)
        interpretation = meaningful_text(parsed.get("interpretation"))
        applied_actions = [
            action.strip()
            for action in planning_actions
            if isinstance(action, str) and action.strip()
        ]
        if _requires_financial_implication(applied_actions) and not any(
            marker in interpretation.casefold()
            for marker in (
                "revenue",
                "cost",
                "cash flow",
                "valuation",
                "financial effect",
            )
        ):
            interpretation = (
                "The supplied article evidence does not by itself establish how "
                "the reported event affects revenue, costs, cash flow, or "
                "valuation; a material financial effect therefore remains "
                "uncertain."
            )
        return {
            "specialist": specialist,
            "observations": observations,
            "interpretation": interpretation,
            "uncertainties": meaningful_text_list(parsed.get("uncertainties")),
            "focus": meaningful_text(parsed.get("focus"))
            or meaningful_text(fallback.get("focus")),
            "applied_memory_actions": applied_actions,
        }


def analyze_general_news_article(article: Mapping[str, Any]) -> dict[str, Any]:
    """Build a grounded fallback analysis for general company news."""

    return evidence_based_fallback(
        article,
        specialist="news",
        focus="General company developments and material events.",
    )


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


def _requires_financial_implication(actions: Collection[str]) -> bool:
    text = " ".join(actions).casefold()
    return "material event" in text and any(
        marker in text for marker in ("revenue", "cash flow", "valuation")
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
