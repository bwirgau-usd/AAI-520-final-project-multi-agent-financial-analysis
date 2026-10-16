"""Shared contracts and utilities for external data-source adapters.

Provider-specific authentication, requests, response parsing, and error
translation belong in the corresponding provider package. Domain tools should
consume normalized adapter output rather than importing provider SDKs directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypedDict

Statement = dict[str, dict[str, float | None]]


@dataclass(frozen=True)
class PricePoint:
    """One normalized closing-price observation."""

    date: datetime
    close: float


class NewsArticle(TypedDict, total=False):
    """One normalized article shared by every news provider."""

    title: str
    summary: str
    description: str
    content: str
    publisher: str
    url: str
    published_at: str | None
    author: str | None
    source: str
    raw_text: str
    normalized_text: str
    category: str
    classification_scores: dict[str, int]
    classification_confidence: float
    extracted: dict[str, Any]
    summary_output: dict[str, Any]
    specialist: str
    specialist_analysis: dict[str, Any]
    evaluation: dict[str, Any]
    optimized_analysis: dict[str, Any]
    evaluation_history: list[dict[str, Any]]
    optimization_history: list[dict[str, Any]]
