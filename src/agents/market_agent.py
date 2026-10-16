"""Specialist logic for market-focused news."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def analyze_market_article(article: Mapping[str, Any]) -> dict[str, Any]:
    """Build a grounded fallback analysis for market content."""

    extracted = _mapping(article.get("extracted"))
    return {
        "specialist": "market",
        "observations": [
            f"Market keywords: {_joined(extracted.get('keywords'))}",
            f"Financial figures: {_joined(extracted.get('financial_numbers'))}",
        ],
        "interpretation": "",
        "uncertainties": [],
        "focus": ("Share price, market activity, analyst commentary, and valuation."),
    }


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _joined(value: object) -> str:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return "none"
    return ", ".join(str(item) for item in value) or "none"
