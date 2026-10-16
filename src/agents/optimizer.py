"""Score and refine specialist news analysis from evaluator feedback."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from src.llm import parse_json_object


def evaluate_analysis(
    analysis: Mapping[str, Any],
    *,
    threshold: float = 75,
) -> dict[str, Any]:
    """Apply the notebook's four-part, 100-point analysis rubric."""

    observations = _string_list(analysis.get("observations"))
    interpretation = _string(analysis.get("interpretation"))
    uncertainties = _string_list(analysis.get("uncertainties"))
    score = 0
    feedback: list[str] = []

    if observations:
        score += 25
    else:
        feedback.append("Add concrete observations from the article.")
    if interpretation:
        score += 25
    else:
        feedback.append("Add a clear interpretation.")
    if uncertainties:
        score += 25
    else:
        feedback.append("Identify uncertainty or missing information.")
    if len(observations) >= 2:
        score += 25
    else:
        feedback.append("Include at least two evidence-based observations.")

    return {
        "score": score,
        "passed": score >= threshold,
        "threshold": threshold,
        "feedback": feedback,
    }


class OptimizerAgent:
    """Use evaluator feedback to produce a clearer grounded analysis."""

    def __init__(self, llm: Callable[[str], str]) -> None:
        self._llm = llm

    def optimize(
        self,
        article: Mapping[str, Any],
        analysis: Mapping[str, Any],
        evaluation: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Return one feedback-driven revision of specialist analysis."""

        prompt = f"""
You are optimizing a financial-news analysis.

Original article evidence:
{json.dumps(article, default=str)}

Current analysis:
{json.dumps(analysis, default=str)}

Evaluator result:
{json.dumps(evaluation, default=str)}

Return only JSON with specialist, observations, interpretation, uncertainties,
and improvements.

Use only supplied evidence. Do not invent facts or financial figures, remove
uncertainty, predict stock prices, or recommend buy, sell, or hold.
""".strip()
        fallback = {
            **dict(analysis),
            "improvements": _string_list(evaluation.get("feedback")),
        }
        parsed = parse_json_object(self._llm(prompt), fallback=fallback)
        return {
            "specialist": _string(parsed.get("specialist"))
            or _string(analysis.get("specialist")),
            "observations": _string_list(parsed.get("observations"))
            or _string_list(analysis.get("observations")),
            "interpretation": _string(parsed.get("interpretation"))
            or _string(analysis.get("interpretation")),
            "uncertainties": _string_list(parsed.get("uncertainties"))
            or _string_list(analysis.get("uncertainties")),
            "improvements": _string_list(parsed.get("improvements"))
            or _string_list(evaluation.get("feedback")),
        }


def _string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
