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
Markdown. Use only the supplied observations and cover every available report
field listed below.

Plan:
{json.dumps(plan, default=str)}

Observations:
{json.dumps(observations, default=str)}

Quality reflection:
{json.dumps(reflection, default=str)}

Deterministic validation:
{json.dumps(validation, default=str)}

Use these headings: Company Overview, Price Performance, Valuation and
Profitability, Financial Performance, Cash Flow, Dividend, Risks and
Uncertainties, Data Quality, and Further Research.

When supplied, include:
- company name, symbol, sector, industry, country, current price, market
  capitalization, and enterprise value;
- start and latest prices, one-year return, annualized volatility, maximum
  drawdown, and price observation count;
- trailing and forward P/E, price/sales, profit and operating margins, return
  on equity, and beta;
- revenue, operating income, net income, EBITDA, diluted EPS, and the
  EBITDA/net-income ratio;
- operating cash flow, free cash flow, capital expenditure, and dividend
  yield; and
- validation findings, risks, missing information, and follow-up questions.

Strict rules:
- Do not use outside knowledge, invent or estimate missing values, silently
  correct suspicious values, calculate unsupported correlations, or make
  unsupported predictions.
- Preserve supplied units and make every numerical claim traceable to the
  observations.
- Clearly distinguish facts from interpretation and explicitly flag suspicious
  values as requiring verification.
- Never claim a field is missing when it exists in the observations.
- Discuss operating or free cash flow whenever either is supplied.
- State that the latest price is unavailable when it is missing.
- Do not provide personalized investment advice, guarantees, buy/sell/hold
  language, or an overall investment rating.
""".strip()
        report = self._llm(prompt).strip()
        if not report:
            raise RuntimeError("The synthesis model returned an empty report.")
        return report
