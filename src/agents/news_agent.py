"""Agent responsible for interpreting financial news."""

from __future__ import annotations

from typing import Any

from src.tools.news_tools import articles_retrieved_at, get_company_news
from src.workflows.news_pipeline import run_news_pipeline


def run_news_agent(symbol: str, company_name: str | None = None) -> dict[str, Any]:
    """Retrieve and analyze recent news for a symbol.

    Connects the news retrieval tool to the ingest-to-summarize prompt chain
    and returns structured news intelligence with sources preserved, so the
    Synthesis Agent can cite specific articles.
    """
    articles = get_company_news(symbol, company_name=company_name)
    pipeline_output = run_news_pipeline(symbol, articles)

    sources = [
        {"title": a["title"], "publisher": a["publisher"], "url": a["url"], "date": a["date"]}
        for a in pipeline_output["extracted"]
    ]

    return {
        "symbol": symbol,
        "retrieved_at": articles_retrieved_at(articles),
        "article_count": len(articles),
        "summary": pipeline_output["summary"],
        "classified_articles": pipeline_output["classified"],
        "extracted_facts": pipeline_output["extracted"],
        "sources": sources,
    }
