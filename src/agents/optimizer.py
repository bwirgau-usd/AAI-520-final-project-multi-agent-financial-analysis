"""Score and refine specialist news analysis from evaluator feedback."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from src.agents.analysis_quality import (
    evidence_based_fallback,
    grounded_observations,
    meaningful_text,
    meaningful_text_list,
    substantive_reasoning_score,
)
from src.llm import parse_json_object
from src.reporting.verified_metrics import (
    append_verified_interpretation,
    reconcile_report_financial_values,
)


def evaluate_analysis(
    analysis: Mapping[str, Any],
    *,
    article: Mapping[str, Any] | None = None,
    threshold: float = 75,
) -> dict[str, Any]:
    """Apply the four-part rubric after rejecting placeholders and inventions."""

    observations = meaningful_text_list(analysis.get("observations"))
    rejected_observations: list[str] = []
    if article is not None:
        observations, rejected_observations = grounded_observations(
            observations,
            article,
        )
    interpretation = meaningful_text(analysis.get("interpretation"))
    uncertainties = meaningful_text_list(analysis.get("uncertainties"))
    score = 0
    feedback: list[str] = []

    if observations:
        score += 25
    else:
        feedback.append("Add concrete observations from the article.")
    if rejected_observations:
        feedback.append(
            "Remove or correct observations that are not supported by article evidence."
        )
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

    substantive_score = substantive_reasoning_score(observations, interpretation)
    if score >= threshold and substantive_score < threshold:
        feedback.append(
            "Structural completeness passed, but substantive financial reasoning "
            "or event-significance analysis remains limited."
        )

    return {
        "score": score,
        "score_type": "structural_completeness_and_source_traceability",
        "passed": score >= threshold and bool(observations),
        "threshold": threshold,
        "feedback": feedback,
        "grounded_observations": observations,
        "rejected_observations": rejected_observations,
        "substantive_reasoning_score": substantive_score,
        "substantive_reasoning_passed": substantive_score >= threshold,
        "quality_dimensions": {
            "structural_completeness_and_source_traceability": score,
            "substantive_financial_reasoning_and_event_significance": (
                substantive_score
            ),
        },
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
        evidence_fallback = evidence_based_fallback(
            article,
            specialist=meaningful_text(analysis.get("specialist")) or "news",
            focus=meaningful_text(analysis.get("focus"))
            or "the reported company development",
        )
        fallback = {**evidence_fallback, **dict(analysis)}
        fallback["improvements"] = meaningful_text_list(evaluation.get("feedback"))
        parsed = parse_json_object(self._llm(prompt), fallback=fallback)
        proposed_observations = meaningful_text_list(parsed.get("observations"))
        grounded, _ = grounded_observations(proposed_observations, article)
        if not grounded:
            existing = meaningful_text_list(analysis.get("observations"))
            grounded, _ = grounded_observations(existing, article)
        grounded = list(
            dict.fromkeys([*grounded, *evidence_fallback["observations"]])
        )
        return {
            "specialist": meaningful_text(parsed.get("specialist"))
            or evidence_fallback["specialist"],
            "observations": grounded,
            "interpretation": meaningful_text(parsed.get("interpretation"))
            or evidence_fallback["interpretation"],
            "uncertainties": meaningful_text_list(parsed.get("uncertainties"))
            or evidence_fallback["uncertainties"],
            "improvements": meaningful_text_list(parsed.get("improvements"))
            or meaningful_text_list(evaluation.get("feedback")),
        }

    def optimize_report(
        self,
        symbol: str,
        research_request: str,
        report: str,
        evaluation: Mapping[str, Any],
        observations: Mapping[str, Any],
        specialist_analyses: Mapping[str, Any],
    ) -> str:
        """Revise a complete report from report-level evaluator feedback."""

        prompt = f"""
Revise this complete {symbol} research report so it directly answers the
user's request and addresses the evaluator feedback.

User research request:
{research_request}

Current report:
{report}

Report evaluation:
{json.dumps(evaluation, default=str)}

Grounding observations:
{json.dumps(observations, default=str)}

Specialist analyses:
{json.dumps(specialist_analyses, default=str)}

Return only the revised Markdown report. Preserve valid content and source
attribution. Use only supplied evidence, state uncertainty, and do not add
personalized investment advice or buy/sell/hold language.
""".strip()
        revised = self._llm(prompt).strip()
        reconciled = reconcile_report_financial_values(
            revised or report,
            observations,
        )
        return append_verified_interpretation(reconciled, observations)
