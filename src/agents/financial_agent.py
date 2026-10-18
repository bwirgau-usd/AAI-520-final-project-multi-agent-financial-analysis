"""Specialist logic for earnings-focused news."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from src.agents.analysis_quality import evidence_based_fallback
from src.state import ResearchPlan

Tool = Callable[[str], dict[str, Any]]


class FinancialResearchAgent:
    """Retrieve and interpret statements, growth, cash/debt, and SEC evidence."""

    TOOL_NAMES = (
        "company_info",
        "financials",
        "cash_flow",
        "balance_sheet",
        "financial_growth",
        "sec_edgar",
    )

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
        growth = observations.get("financial_growth")
        financials = observations.get("financials")
        balance = observations.get("balance_sheet")
        balance_latest = (
            balance.get("latest", {}) if isinstance(balance, Mapping) else {}
        )
        balance_trends = (
            balance.get("trends", {}) if isinstance(balance, Mapping) else {}
        )
        return {
            "specialist": "financial",
            "observations": observations,
            "analysis": {
                "operating_expenses": (
                    dict(financials.get("Operating Expenses", {}))
                    if isinstance(financials, Mapping)
                    and isinstance(financials.get("Operating Expenses"), Mapping)
                    else {}
                ),
                "growth": dict(growth) if isinstance(growth, Mapping) else {},
                "cash_and_debt": (
                    dict(balance_latest)
                    if isinstance(balance_latest, Mapping)
                    else {}
                ),
                "balance_sheet_trends": (
                    dict(balance_trends)
                    if isinstance(balance_trends, Mapping)
                    else {}
                ),
                "has_sec_evidence": bool(
                    isinstance(observations.get("sec_edgar"), Mapping)
                    and not observations["sec_edgar"].get("error")
                ),
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
            progress(f"Running financial tool: {name}")
        try:
            results[name] = tools[name](symbol)
        except Exception as exc:  # noqa: BLE001 - isolate provider failures
            results[name] = {"error": f"{type(exc).__name__}: {exc}"}
    return results


def analyze_earnings_article(article: Mapping[str, Any]) -> dict[str, Any]:
    """Build a grounded fallback analysis for earnings content."""

    return evidence_based_fallback(
        article,
        specialist="earnings",
        focus="Revenue, earnings, EPS, profitability, and guidance.",
    )


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _joined(value: object) -> str:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return "none"
    return ", ".join(str(item) for item in value) or "none"
