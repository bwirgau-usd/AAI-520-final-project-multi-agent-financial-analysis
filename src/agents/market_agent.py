"""Specialist logic for market-focused news."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from src.state import ResearchPlan

Tool = Callable[[str], dict[str, Any]]


class MarketResearchAgent:
    """Retrieve and interpret the market evidence needed by synthesis."""

    TOOL_NAMES = ("price_data", "company_info")

    def research(
        self,
        symbol: str,
        plan: ResearchPlan,
        tools: Mapping[str, Tool],
        *,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        selected = [name for name in plan.get("tools", []) if name in self.TOOL_NAMES]
        observations = _run_tools(symbol, selected, tools, progress)
        price = observations.get("price_data")
        metrics = dict(price) if isinstance(price, Mapping) else {}
        return {
            "specialist": "market",
            "observations": observations,
            "analysis": {
                "performance": {
                    key: metrics.get(key)
                    for key in (
                        "1m_return_percent",
                        "3m_return_percent",
                        "1y_return_percent",
                    )
                },
                "risk": {
                    "annualized_volatility_percent": metrics.get(
                        "annualized_volatility_percent"
                    ),
                    "maximum_drawdown_percent": metrics.get(
                        "maximum_drawdown_percent"
                    ),
                },
                "range_and_volume": {
                    key: metrics.get(key)
                    for key in (
                        "52_week_high",
                        "52_week_low",
                        "latest_volume",
                        "average_volume",
                    )
                },
            },
            "source_tools": selected,
        }


def _run_tools(
    symbol: str,
    selected: Sequence[str],
    tools: Mapping[str, Tool],
    progress: Callable[[str], None] | None,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name in selected:
        if progress:
            progress(f"Running market tool: {name}")
        try:
            results[name] = tools[name](symbol)
        except Exception as exc:  # noqa: BLE001 - isolate provider failures
            results[name] = {"error": f"{type(exc).__name__}: {exc}"}
    return results


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
