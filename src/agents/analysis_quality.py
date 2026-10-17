"""Shared normalization and grounding checks for article analysis."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

PLACEHOLDER_VALUES = frozenset(
    {
        "",
        "-",
        "--",
        "[]",
        "{}",
        "n/a",
        "na",
        "nil",
        "none",
        "not available",
        "not applicable",
        "null",
        "undefined",
        "unknown",
    }
)

_LABEL_PREFIX = re.compile(
    r"^(?:observation|headlines?|financial figures?(?: reported)?|figures?|"
    r"detected events?|events?|keywords?|market keywords?|source(?: and date)?|"
    r"interpretation|uncertaint(?:y|ies))\s*:\s*",
    flags=re.IGNORECASE,
)
_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?%?", flags=re.IGNORECASE)
_NUMBER = re.compile(r"(?<![a-z])[-+]?\$?\d[\d,.]*(?:%|\s*(?:billion|million|thousand|b|m|k))?", flags=re.IGNORECASE)
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "article",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "reports",
        "reported",
        "says",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "with",
    }
)

_METADATA_OBSERVATION_PREFIXES = (
    "headline:",
    "source:",
    "source and date:",
)
_GENERIC_INTERPRETATION_PHRASES = (
    "provides evidence relevant to",
    "requires corroboration",
    "too limited for a supported interpretation",
)
_REASONING_MARKERS = (
    "because",
    "therefore",
    "suggest",
    "indicat",
    "imply",
    "impact",
    "risk",
    "margin",
    "revenue",
    "earnings",
    "cash flow",
    "debt",
    "valuation",
)


def meaningful_text(value: object) -> str:
    """Return normalized text, rejecting null-like placeholders."""

    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text:
        return ""
    candidate = _LABEL_PREFIX.sub("", text).strip().strip("-–—:;,. ")
    if candidate.casefold() in PLACEHOLDER_VALUES:
        return ""
    return text


def meaningful_text_list(value: object) -> list[str]:
    """Return only substantive strings from a list-like model field."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [text for item in value if (text := meaningful_text(item))]


def grounded_observations(
    observations: object,
    article: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    """Partition observations by whether the article contains their evidence."""

    accepted: list[str] = []
    rejected: list[str] = []
    evidence = article_evidence_text(article)
    evidence_tokens = set(_tokens(evidence))
    normalized_evidence = _normalize_number_text(evidence)

    for observation in meaningful_text_list(observations):
        content = _LABEL_PREFIX.sub("", observation).strip()
        numbers = [_normalize_number_text(item) for item in _NUMBER.findall(content)]
        content_tokens = [
            token
            for token in _tokens(content)
            if token not in _STOPWORDS and len(token) >= 3
        ]
        word_tokens = [token for token in content_tokens if not token[0].isdigit()]
        overlap = sum(token in evidence_tokens for token in set(word_tokens))
        figures_grounded = all(number in normalized_evidence for number in numbers)
        required_overlap = max(1, math.ceil(0.8 * len(set(word_tokens))))
        is_grounded = bool(content_tokens) and figures_grounded and (
            overlap >= required_overlap
        )
        (accepted if is_grounded else rejected).append(observation)
    return accepted, rejected


def substantive_reasoning_score(
    observations: object,
    interpretation: object,
) -> int:
    """Score financial substance separately from structural completeness.

    Headline and source metadata are useful for traceability, but they do not
    themselves demonstrate financial reasoning. This deliberately small rubric
    makes that distinction visible without changing the structural gate used by
    the optimizer loop.
    """

    evidence = meaningful_text_list(observations)
    substantive_evidence = [
        item
        for item in evidence
        if not item.casefold().startswith(_METADATA_OBSERVATION_PREFIXES)
    ]
    interpretation_text = meaningful_text(interpretation).casefold()
    is_generic = any(
        phrase in interpretation_text
        for phrase in _GENERIC_INTERPRETATION_PHRASES
    )
    has_reasoning = any(
        marker in interpretation_text for marker in _REASONING_MARKERS
    )
    return (50 if substantive_evidence else 0) + (
        50 if interpretation_text and not is_generic and has_reasoning else 0
    )


def evidence_based_fallback(
    article: Mapping[str, Any],
    *,
    specialist: str,
    focus: str,
) -> dict[str, Any]:
    """Create a useful deterministic analysis using only visible article fields."""

    title = meaningful_text(article.get("title"))
    source = meaningful_text(article.get("source") or article.get("publisher"))
    published = meaningful_text(article.get("published_at") or article.get("date"))
    extracted = article.get("extracted")
    fields = extracted if isinstance(extracted, Mapping) else {}
    figures = meaningful_text_list(fields.get("financial_numbers"))
    events = meaningful_text_list(fields.get("events"))

    candidates: list[str] = []
    if title:
        candidates.append(f"Headline: {title}")
    if figures:
        candidates.append(f"Financial figures reported: {', '.join(figures)}")
    if events:
        candidates.append(f"Detected events: {', '.join(events)}")
    if source and published:
        candidates.append(f"Source and date: {source}, {published}")
    elif source:
        candidates.append(f"Source: {source}")

    observations, _ = grounded_observations(candidates, article)
    if not observations and title:
        observations = [title]
    interpretation = (
        f"The supplied article provides evidence relevant to {focus.lower()}; "
        "its investment significance requires corroboration with primary financial data."
        if observations
        else "The available article payload is too limited for a supported interpretation."
    )
    return {
        "specialist": specialist,
        "observations": observations,
        "interpretation": interpretation,
        "uncertainties": [
            "The provider payload may contain only a headline or snippet; verify the linked source."
        ],
        "focus": focus,
    }


def article_evidence_text(article: Mapping[str, Any]) -> str:
    """Flatten original and extracted article fields for deterministic matching."""

    evidence_fields = {
        key: article.get(key)
        for key in (
            "title",
            "summary",
            "description",
            "content",
            "raw_text",
            "normalized_text",
            "source",
            "publisher",
            "published_at",
            "date",
        )
    }
    return json.dumps(evidence_fields, default=str, ensure_ascii=False).casefold()


def _tokens(value: str) -> list[str]:
    return [token.casefold() for token in _TOKEN.findall(value)]


def _normalize_number_text(value: str) -> str:
    return re.sub(r"[\s,$]", "", value.casefold())
