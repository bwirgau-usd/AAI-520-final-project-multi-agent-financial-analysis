"""Create concise, actionable notes for future research runs."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from src.state import Reflection


class MemoryCurator:
    """Summarize reusable lessons without treating them as live evidence."""

    def __init__(self, llm: Callable[[str], str]) -> None:
        self._llm = llm

    def summarize(
        self,
        symbol: str,
        report: str,
        reflection: Reflection,
        report_evaluation: Mapping[str, Any] | None = None,
        research_request: str = "",
    ) -> str:
        """Return a short note suitable for the persistent memory store."""

        prompt = f"""
Summarize reusable research lessons from this {symbol} run in at most 120 words.
Focus on evidence coverage, data-quality problems, and improvements for a future
run. Do not present time-sensitive values as permanent facts.

Research request:
{research_request}

Reflection:
{json.dumps(reflection, default=str)}

Complete-report evaluation:
{json.dumps(report_evaluation or {}, default=str)}

Report:
{report}
""".strip()
        summary = self._llm(prompt).strip()
        if not summary:
            raise RuntimeError("The memory model returned an empty summary.")
        return summary

    def curate(
        self,
        symbol: str,
        report: str,
        reflection: Reflection,
        report_evaluation: Mapping[str, Any] | None = None,
        research_request: str = "",
        news_analysis: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a readable summary plus machine-actionable lessons.

        The prose summary remains useful to reviewers. Structured lessons make
        the causal path inspectable: weakness -> next-run action -> success
        check. Lesson generation is deterministic so it remains available when
        the summarization model returns prose instead of JSON.
        """

        summary = self.summarize(
            symbol,
            report,
            reflection,
            report_evaluation,
            research_request,
        )
        weaknesses = self._candidate_weaknesses(
            reflection,
            report_evaluation or {},
            news_analysis or {},
        )
        return {
            "summary": summary,
            "lessons": [_actionable_lesson(item) for item in weaknesses[:5]],
        }

    @staticmethod
    def _candidate_weaknesses(
        reflection: Reflection,
        report_evaluation: Mapping[str, Any],
        news_analysis: Mapping[str, Any],
    ) -> list[str]:
        candidates = [
            *reflection.get("weaknesses", []),
            *reflection.get("missing_information", []),
        ]
        candidates.extend(
            item
            for item in report_evaluation.get("feedback", [])
            if isinstance(item, str)
            and item.strip()
            and not item.casefold().startswith("improve ")
            and not item.casefold().startswith("no report can pass")
        )

        articles = news_analysis.get("articles", [])
        if isinstance(articles, list) and any(
            _initial_reasoning_is_weak(article) for article in articles
        ):
            candidates.insert(0, "News analysis lacks financial implications")

        unique: list[str] = []
        for item in candidates:
            text = str(item).strip()
            if text and text.casefold() not in {value.casefold() for value in unique}:
                unique.append(text)
        return unique


def _initial_reasoning_is_weak(article: object) -> bool:
    if not isinstance(article, Mapping):
        return False
    history = article.get("evaluation_history", [])
    evaluation = history[0] if isinstance(history, list) and history else article.get(
        "evaluation", {}
    )
    return bool(
        isinstance(evaluation, Mapping)
        and float(evaluation.get("substantive_reasoning_score", 0) or 0) < 60
    )


def _actionable_lesson(weakness: str) -> dict[str, str]:
    """Map common evaluator weaknesses to concrete next-run behavior."""

    normalized = weakness.casefold().replace("-", " ")
    if any(
        marker in normalized
        for marker in (
            "financial implication",
            "financial reasoning",
            "event significance",
            "reasoning remains limited",
        )
    ):
        return {
            "weakness": weakness,
            "next_run_action": (
                "Explain how each material event could affect revenue, costs, "
                "cash flow, or valuation"
            ),
            "success_check": (
                "Include supporting article evidence, a financial implication, "
                "and uncertainty; state explicitly when no material effect is "
                "established"
            ),
        }
    if any(
        marker in normalized
        for marker in (
            "source traceability",
            "primary source",
            "citation",
            "source link",
            "sources; current score",
        )
    ):
        return {
            "weakness": weakness,
            "next_run_action": (
                "Link each material claim to a filing-level citation or provider "
                "source URL"
            ),
            "success_check": (
                "Every material claim names its evidence source and available link"
            ),
        }
    if "volatility" in normalized or "drawdown" in normalized:
        return {
            "weakness": weakness,
            "next_run_action": (
                "Add period-specific volatility and drawdown context to the market "
                "interpretation"
            ),
            "success_check": (
                "The report connects observed volatility and drawdown to risk with "
                "their periods and values"
            ),
        }
    return {
        "weakness": weakness,
        "next_run_action": f"Address this evaluator finding explicitly: {weakness}",
        "success_check": (
            "The next report supplies relevant evidence and states remaining "
            "uncertainty for this finding"
        ),
    }
