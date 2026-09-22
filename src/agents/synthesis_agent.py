"""Agent responsible for synthesizing research findings."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from src.state import Reflection, ResearchPlan, ValidationIssue


class SynthesisAgent:
    """Convert the plan, evidence, and evaluation into a readable report."""

    def __init__(self, llm: Callable[[str], str]) -> None:
        self._llm = llm

    def create_report(
        self,
        symbol: str,
        plan: ResearchPlan,
        observations: Mapping[str, Any],
        reflection: Reflection,
        validation: list[ValidationIssue],
    ) -> str:
        """Generate a grounded Markdown research report."""

        prompt = f"""
Write a concise, evidence-based investment research report for {symbol} in
Markdown. Use only the supplied observations. Clearly distinguish facts from
interpretation, identify risks and missing data, and do not provide personalized
investment advice or guarantees.

Plan:
{json.dumps(plan, default=str)}

Observations:
{json.dumps(observations, default=str)}

Quality reflection:
{json.dumps(reflection, default=str)}

Deterministic validation:
{json.dumps(validation, default=str)}

Use these headings: Company Overview, Price Performance, Valuation, Financial
Performance, Cash Flow, Risks and Uncertainties, Data Quality, and Further
Research. Mention unavailable or suspicious evidence explicitly.
""".strip()
        report = self._llm(prompt).strip()
        if not report:
            raise RuntimeError("The synthesis model returned an empty report.")
        return report
