"""Prompt chaining, routing, evaluation, and optimization for company news."""

from __future__ import annotations

import os
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.agents import NewsAgent, OptimizerAgent, SpecialistRouter
from src.agents.optimizer import evaluate_analysis
from src.data_sources.base import NewsArticle
from src.data_sources.google_news import GoogleNewsClient
from src.data_sources.news_api import NewsApiClient
from src.data_sources.yahoo_finance import YahooFinanceClient
from src.llm import ask_llm, parse_json_object
from src.tools.news_tools import (
    GoogleNewsDataClient,
    NewsApiDataClient,
    YahooNewsClient,
    ingest_news,
    preprocess_article,
    prompt_classify_article,
    prompt_extract_information,
    prompt_summarize_article,
)

ProgressCallback = Callable[[str], None]
LlmCallable = Callable[[str], str]


@dataclass
class NewsPipeline:
    """Run the complete news workflow extracted from the legacy notebook."""

    yahoo_client: YahooNewsClient
    news_api_client: NewsApiDataClient
    router: SpecialistRouter
    analyst: NewsAgent
    optimizer: OptimizerAgent
    google_news_client: GoogleNewsDataClient | None = None
    max_articles: int = 8
    evaluation_threshold: float = 75
    max_optimizer_iterations: int = 3
    prompt_llm: LlmCallable = ask_llm

    def analyze(
        self,
        symbol: str,
        research_request: str = "",
        *,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Return articles plus source, routing, and evaluation summaries."""

        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must be a non-empty string")
        emit = progress or (lambda _message: None)

        ingestion = ingest_news(
            self.yahoo_client,
            self.news_api_client,
            normalized_symbol,
            google_news_client=self.google_news_client,
            max_articles=self.max_articles,
        )
        raw_articles = ingestion["articles"]
        processed_articles: list[NewsArticle] = []

        for index, raw_article in enumerate(raw_articles, start=1):
            emit(f"Processing news article {index}/{len(raw_articles)}")
            article = preprocess_article(raw_article)
            article = prompt_classify_article(
                article,
                self.prompt_llm,
                research_request,
            )
            article = prompt_extract_information(article, self.prompt_llm)
            article = prompt_summarize_article(article, self.prompt_llm)
            article = self.router.route(article)

            fallback = article["specialist_analysis"]
            try:
                initial_analysis = self.analyst.analyze(
                    article,
                    fallback,
                    research_request,
                )
            except Exception as exc:  # noqa: BLE001 - isolate an article/model failure
                initial_analysis = {
                    **fallback,
                    "uncertainties": [
                        *list(fallback.get("uncertainties", [])),
                        f"Specialist model unavailable: {type(exc).__name__}: {exc}",
                    ],
                }

            current_analysis = initial_analysis
            evaluation = evaluate_analysis(
                current_analysis,
                threshold=self.evaluation_threshold,
            )
            evaluation_history = [evaluation]
            optimization_history: list[dict[str, Any]] = []

            iterations = 0
            while (
                not evaluation["passed"] and iterations < self.max_optimizer_iterations
            ):
                try:
                    current_analysis = self.optimizer.optimize(
                        article,
                        current_analysis,
                        evaluation,
                    )
                except Exception as exc:  # noqa: BLE001 - preserve prior analysis
                    current_analysis = {
                        **current_analysis,
                        "improvements": [
                            f"Optimizer unavailable: {type(exc).__name__}: {exc}"
                        ],
                    }
                    optimization_history.append(current_analysis)
                    break
                optimization_history.append(current_analysis)
                evaluation = evaluate_analysis(
                    current_analysis,
                    threshold=self.evaluation_threshold,
                )
                evaluation_history.append(evaluation)
                iterations += 1

            article["specialist_analysis"] = initial_analysis
            article["evaluation"] = evaluation
            article["optimized_analysis"] = current_analysis
            article["evaluation_history"] = evaluation_history
            article["optimization_history"] = optimization_history
            processed_articles.append(article)

        source_counts = Counter(
            str(article.get("source") or "Unknown") for article in processed_articles
        )
        routing_counts = Counter(
            str(article.get("category") or "unknown") for article in processed_articles
        )
        scores = [
            float(article["evaluation"].get("score", 0))
            for article in processed_articles
        ]
        return {
            "ticker": normalized_symbol,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "pipeline_stages": [
                "ingest",
                "preprocess",
                "classify",
                "extract",
                "summarize",
                "route",
                "specialist",
                "evaluate",
                "optimize",
            ],
            "articles": processed_articles,
            "article_count": len(processed_articles),
            "retrieved_counts": ingestion["retrieved_counts"],
            "source_errors": ingestion["source_errors"],
            "source_counts": dict(source_counts),
            "routing_counts": dict(routing_counts),
            "average_score": sum(scores) / len(scores) if scores else None,
            "passed_count": sum(
                bool(article["evaluation"].get("passed"))
                for article in processed_articles
            ),
            "evaluation_threshold": self.evaluation_threshold,
            "max_optimizer_iterations": self.max_optimizer_iterations,
        }


def build_news_pipeline(
    llm: LlmCallable,
    *,
    yahoo_client: YahooNewsClient | None = None,
    news_api_client: NewsApiDataClient | None = None,
    google_news_client: GoogleNewsDataClient | None = None,
    max_articles: int | None = None,
    evaluation_threshold: float | None = None,
    max_optimizer_iterations: int | None = None,
) -> NewsPipeline:
    """Build the production pipeline with environment-configured limits."""

    threshold = (
        evaluation_threshold
        if evaluation_threshold is not None
        else _float_env("EVALUATION_SCORE_THRESHOLD", 0.8)
    )
    if threshold <= 1:
        threshold *= 100
    resolved_yahoo = yahoo_client or YahooFinanceClient()

    def resolve_company_name(symbol: str) -> str | None:
        get_company_info = getattr(resolved_yahoo, "get_company_info", None)
        if not callable(get_company_info):
            return None
        info = get_company_info(symbol)
        return str(info.get("longName") or info.get("shortName") or "") or None

    resolved_google = google_news_client
    if resolved_google is None and yahoo_client is None and news_api_client is None:
        resolved_google = GoogleNewsClient(company_name_resolver=resolve_company_name)

    return NewsPipeline(
        yahoo_client=resolved_yahoo,
        news_api_client=news_api_client
        or NewsApiClient(company_name_resolver=resolve_company_name),
        google_news_client=resolved_google,
        router=SpecialistRouter(),
        analyst=NewsAgent(llm),
        optimizer=OptimizerAgent(llm),
        max_articles=max_articles
        if max_articles is not None
        else _int_env("MAX_NEWS_ARTICLES", 16),
        evaluation_threshold=max(0, min(float(threshold), 100)),
        max_optimizer_iterations=(
            max_optimizer_iterations
            if max_optimizer_iterations is not None
            else _int_env("MAX_OPTIMIZER_ITERATIONS", 3)
        ),
        prompt_llm=llm,
    )


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Compatibility prompt chain from the merged NewsAPI pull request.
# ---------------------------------------------------------------------------

NEWS_CATEGORIES = [
    "EARNINGS",
    "PRODUCT",
    "REGULATORY",
    "MARKET",
    "LEGAL",
    "OTHER",
]
_WHITESPACE_RE = re.compile(r"\s+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _chat_json(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Call the configured local model without failing the article batch."""

    try:
        response = ask_llm(f"{system_prompt}\n\n{user_prompt}")
    except Exception:  # noqa: BLE001 - preserve documented safe defaults
        return {}
    return parse_json_object(response, fallback={})


def ingest(
    articles: list[dict[str, Any]],
    max_articles: int = 10,
) -> list[dict[str, Any]]:
    """Cap the compatibility article set to a workable batch size."""

    return articles[: max(0, int(max_articles))]


def preprocess(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate titles and clean compatibility-schema article text."""

    seen_titles: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for article in articles:
        title = str(article.get("title") or "").strip()
        normalized_title = title.lower()
        if not title or normalized_title in seen_titles:
            continue
        seen_titles.add(normalized_title)
        text = _HTML_TAG_RE.sub(" ", str(article.get("text") or ""))
        text = _WHITESPACE_RE.sub(" ", text).strip()
        if text:
            cleaned.append({**article, "title": title, "text": text})
    return cleaned


def classify(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign an LLM category while retaining deterministic defaults."""

    system_prompt = (
        "Classify financial news into exactly one category from "
        f"{NEWS_CATEGORIES}. Respond with JSON containing category and "
        "confidence."
    )
    classified = []
    for article in articles:
        result = _chat_json(
            system_prompt,
            f"Title: {article['title']}\nText: {article['text'][:1000]}",
        )
        classified.append(
            {
                **article,
                "category": result.get("category", "OTHER"),
                "confidence": result.get("confidence", 0.0),
            }
        )
    return classified


def extract(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract compatibility-schema facts with safe fallback values."""

    system_prompt = (
        "Extract company, event, dates, numbers, and sentiment from this "
        "financial article. Respond with one JSON object."
    )
    extracted = []
    for article in articles:
        result = _chat_json(
            system_prompt,
            f"Title: {article['title']}\nText: {article['text'][:1500]}",
        )
        extracted.append(
            {
                **article,
                "company": result.get("company"),
                "event": result.get("event"),
                "dates": result.get("dates", []),
                "numbers": result.get("numbers", []),
                "sentiment": result.get("sentiment", "neutral"),
            }
        )
    return extracted


def summarize(symbol: str, articles: list[dict[str, Any]]) -> str:
    """Produce a short cross-article compatibility summary."""

    if not articles:
        return f"No recent news articles were available for {symbol}."
    digest = "\n".join(
        f"- [{article.get('category', 'OTHER')}] {article['title']} "
        f"({article.get('sentiment', 'neutral')})"
        for article in articles
    )
    result = _chat_json(
        "Summarize recent company news in 3-5 grounded sentences. Respond "
        "with JSON containing summary.",
        f"Symbol: {symbol}\nArticles:\n{digest}",
    )
    return str(
        result.get("summary") or f"Unable to generate a news summary for {symbol}."
    )


def run_news_pipeline(
    symbol: str,
    raw_articles: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run every stage of the compatibility prompt chain."""

    ingested = ingest(raw_articles)
    preprocessed = preprocess(ingested)
    classified = classify(preprocessed)
    extracted = extract(classified)
    return {
        "ingested": ingested,
        "preprocessed": preprocessed,
        "classified": classified,
        "extracted": extracted,
        "summary": summarize(symbol, extracted),
    }
