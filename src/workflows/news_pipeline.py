"""Prompt-chaining workflow for processing financial news.

Stages run in sequence, each consuming the previous stage's structured
output: Ingest -> Preprocess -> Classify -> Extract -> Summarize. Every stage
is a plain function so intermediate outputs can be inspected and displayed in
the project notebook.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

NEWS_CATEGORIES = ["EARNINGS", "PRODUCT", "REGULATORY", "MARKET", "LEGAL", "OTHER"]

_WHITESPACE_RE = re.compile(r"\s+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _chat_json(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Call the LLM and parse a JSON object response.

    Returns an empty dict if the API key is missing or the call fails, so a
    single article's failure does not stop the rest of the pipeline.
    """
    try:
        response = _client().chat.completions.create(
            model=_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return json.loads(response.choices[0].message.content)
    except Exception:  # noqa: BLE001 - a single stage failure should not stop the pipeline
        return {}


def ingest(articles: list[dict[str, Any]], max_articles: int = 10) -> list[dict[str, Any]]:
    """Stage 1: cap the article set to a workable batch size."""
    return articles[:max_articles]


def preprocess(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stage 2: dedupe, clean, and normalize article text."""
    seen_titles: set[str] = set()
    cleaned: list[dict[str, Any]] = []

    for article in articles:
        title = (article.get("title") or "").strip()
        normalized_title = title.lower()
        if not title or normalized_title in seen_titles:
            continue
        seen_titles.add(normalized_title)

        text = _HTML_TAG_RE.sub(" ", article.get("text") or "")
        text = _WHITESPACE_RE.sub(" ", text).strip()
        if not text:
            continue

        cleaned.append({**article, "title": title, "text": text})

    return cleaned


def classify(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stage 3: assign each article a category and confidence score."""
    system_prompt = (
        "You classify financial news headlines into exactly one category from "
        f"{NEWS_CATEGORIES}. Respond with JSON: "
        '{"category": "<CATEGORY>", "confidence": <0-1 float>}.'
    )

    classified = []
    for article in articles:
        user_prompt = f"Title: {article['title']}\nText: {article['text'][:1000]}"
        result = _chat_json(system_prompt, user_prompt)
        classified.append(
            {
                **article,
                "category": result.get("category", "OTHER"),
                "confidence": result.get("confidence", 0.0),
            }
        )
    return classified


def extract(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stage 4: pull structured facts out of each classified article."""
    system_prompt = (
        "Extract structured facts from a financial news article. Respond with "
        "JSON: {\"company\": <str>, \"event\": <short str>, \"dates\": [<str>], "
        '"numbers": [<str>], "sentiment": "<positive|negative|neutral>"}.'
    )

    extracted = []
    for article in articles:
        user_prompt = f"Title: {article['title']}\nText: {article['text'][:1500]}"
        result = _chat_json(system_prompt, user_prompt)
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
    """Stage 5: produce a short narrative summary across all articles."""
    if not articles:
        return f"No recent news articles were available for {symbol}."

    system_prompt = (
        "Summarize recent company news for an investment research report in "
        "3-5 sentences. Ground every claim in the provided articles and note "
        "conflicting signals if present. Respond with JSON: {\"summary\": <str>}."
    )
    digest = "\n".join(
        f"- [{a.get('category', 'OTHER')}] {a['title']} ({a.get('sentiment', 'neutral')})"
        for a in articles
    )
    result = _chat_json(system_prompt, f"Symbol: {symbol}\nArticles:\n{digest}")
    return result.get("summary", f"Unable to generate a news summary for {symbol}.")


def run_news_pipeline(symbol: str, raw_articles: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the full ingest-to-summarize chain and return every stage's output."""
    ingested = ingest(raw_articles)
    preprocessed = preprocess(ingested)
    classified = classify(preprocessed)
    extracted = extract(classified)
    final_summary = summarize(symbol, extracted)

    return {
        "ingested": ingested,
        "preprocessed": preprocessed,
        "classified": classified,
        "extracted": extracted,
        "summary": final_summary,
    }
