"""Agent responsible for synthesizing research findings."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from src.reporting.verified_metrics import (
    reconcile_report_financial_values,
    verified_financial_metrics,
)
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
        research_request: str = "",
        specialist_analyses: Mapping[str, Any] | None = None,
    ) -> str:
        """Generate a grounded Markdown research report."""

        verified_metrics = verified_financial_metrics(observations)

        prompt = f"""
Write a concise, evidence-based investment research report for {symbol} in
Markdown. Use only the supplied observations and cover every available report
field listed below.

User research request:
{research_request or 'Provide a comprehensive investment research report.'}

Plan:
{json.dumps(plan, default=str)}

Observations:
{json.dumps(observations, default=str)}

Quality reflection:
{json.dumps(reflection, default=str)}

Deterministic validation:
{json.dumps(validation, default=str)}

Specialist analyses:
{json.dumps(specialist_analyses or {}, default=str)}

Canonical financial metrics (copy these formatted values exactly; never
recalculate, rescale, abbreviate, or change their digits):
{json.dumps(verified_metrics, default=str)}

Use these headings: Company Overview, Price Performance, Valuation and
Profitability, Financial Performance, Cash Flow, SEC EDGAR Evidence, Dividend,
Recent News and Catalysts, Risks and Uncertainties, Data Quality, and
Further Research.

When supplied, include:
- company name, symbol, sector, industry, country, current price, market
  capitalization, and enterprise value;
- start and latest prices, one-year return, annualized volatility, maximum
  drawdown, one-month and three-month returns, 52-week high and low, latest
  and average trading volume, and price observation count;
- trailing and forward P/E, price/sales, profit and operating margins, return
  on equity, and beta;
- revenue, operating expenses, operating income, net income, EBITDA, diluted
  EPS, and the EBITDA/net-income ratio;
- operating cash flow, free cash flow, capital expenditure, and dividend
  yield;
- balance-sheet cash, debt, net debt, cash/debt ratio, assets, liabilities,
  equity, and deterministic revenue, net-income, and diluted-EPS growth;
- SEC entity name, CIK, SIC classification, every supplied official company
  fact with its period, filing metadata, and recent 10-K, 10-Q, and 8-K links;
- news source and publisher, publication date, headline and URL, detected
  events and figures, routed specialist, evaluator score and feedback, final
  optimized observations, interpretation, uncertainties, source/routing
  totals, and average evaluation score; and
- validation findings, risks, missing information, and follow-up questions.

Strict rules:
- Do not use outside knowledge, invent or estimate missing values, silently
  correct suspicious values, calculate unsupported correlations, or make
  unsupported predictions.
- Preserve supplied units and make every numerical claim traceable to the
  observations.
- Treat the canonical financial metrics as authoritative. Do not perform
  arithmetic on financial-statement values or dividend yield.
- State verification scope precisely: SEC facts provide primary-source evidence
  for selected financial metrics; market data and news are provider-supplied and
  require independent verification. Never claim all data was verified.
- When provider and SEC balance-sheet values use different reporting periods,
  label both periods and explain that they are not the same snapshot.
- Describe article evaluator scores as structural completeness and source
  traceability. Discuss the separate substantive financial-reasoning and
  event-significance score; a 100 structural score is not perfect analysis.
- Clearly distinguish facts from interpretation and explicitly flag suspicious
  values as requiring verification.
- Never claim a field is missing when it exists in the observations.
- Discuss operating or free cash flow whenever either is supplied.
- State that the latest price is unavailable when it is missing.
- Do not provide personalized investment advice, guarantees, buy/sell/hold
  language, or an overall investment rating.
- Directly answer the user's research request and identify which specialist
  evidence supports each material conclusion.
""".strip()
        report = self._llm(prompt).strip()
        if not report:
            raise RuntimeError("The synthesis model returned an empty report.")
        return reconcile_report_financial_values(report, observations)
