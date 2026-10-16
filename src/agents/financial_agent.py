"""Specialist logic for earnings-focused news."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def analyze_earnings_article(article: Mapping[str, Any]) -> dict[str, Any]:
    """Build a grounded fallback analysis for earnings content."""

    extracted = _mapping(article.get("extracted"))
    return {
        "specialist": "earnings",
        "observations": [
            f"Financial figures: {_joined(extracted.get('financial_numbers'))}",
            f"Events: {_joined(extracted.get('events'))}",
        ],
        "interpretation": "",
        "uncertainties": [],
        "focus": "Revenue, earnings, EPS, profitability, and guidance.",
    }


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _joined(value: object) -> str:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return "none"
    return ", ".join(str(item) for item in value) or "none"
