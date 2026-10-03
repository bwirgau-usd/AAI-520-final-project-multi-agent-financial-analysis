"""Deterministic text presentation for a completed research workflow."""

from __future__ import annotations

import re
from collections.abc import Mapping
from numbers import Number
from typing import Any

from src.state import ResearchState


def render_console_summary(state: ResearchState) -> str:
    """Render the notebook's former console report without printing it."""

    symbol = state.get("symbol", "UNKNOWN")
    observations = state.get("observations", {})
    price = _mapping(observations.get("price_data"))
    info = _mapping(observations.get("company_info"))
    financials = _mapping(observations.get("financials"))
    cash_flow = _mapping(observations.get("cash_flow"))
    sec_edgar = _mapping(observations.get("sec_edgar"))
    validation = state.get("validation", [])
    report_validation = state.get("report_validation", [])
    reflection = _mapping(state.get("reflection"))
    plan = _mapping(state.get("plan"))
    period = _latest_period(financials, cash_flow)
    period_label = _period_label(period)

    current_price = price.get("latest_price")
    if current_price is None:
        current_price = info.get("currentPrice")
    revenue = _statement_value(financials, "Total Revenue", period)
    operating_income = _statement_value(financials, "Operating Income", period)
    net_income = _statement_value(financials, "Net Income", period)
    ebitda = _statement_value(financials, "EBITDA", period)
    diluted_eps = _statement_value(financials, "Diluted EPS", period)
    operating_cash = _statement_value(cash_flow, "Operating Cash Flow", period)
    free_cash = _statement_value(cash_flow, "Free Cash Flow", period)
    capital_expenditure = _statement_value(
        cash_flow,
        "Capital Expenditure",
        period,
    )

    lines = [
        "=" * 70,
        "FINAL RESEARCH REPORT",
        "=" * 70,
        "",
        f"{info.get('longName') or symbol} ({symbol})",
        "-" * 70,
        "",
        "1. COMPANY OVERVIEW",
        f"   Sector:              {_text(info.get('sector'))}",
        f"   Industry:            {_text(info.get('industry'))}",
        f"   Country:             {_text(info.get('country'))}",
        f"   Current Price:       {_currency(current_price)}",
        f"   Market Cap:          {_large_currency(info.get('marketCap'))}",
        f"   Enterprise Value:    {_large_currency(info.get('enterpriseValue'))}",
        "",
        "2. PRICE PERFORMANCE",
        f"   Start Price:         {_currency(price.get('start_price'))}",
        f"   Latest Price:        {_currency(price.get('latest_price'))}",
        f"   One-Year Return:     {_percentage_points(price.get('1y_return_percent'))}",
        (
            "   Annualized Volatility: "
            f"{_percentage_points(price.get('annualized_volatility_percent'))}"
        ),
        (
            "   Maximum Drawdown:    "
            f"{_percentage_points(price.get('maximum_drawdown_percent'))}"
        ),
        f"   Observations:        {_number(price.get('observations'), 0)}",
        "",
        "3. VALUATION",
        f"   Trailing P/E:        {_number(info.get('trailingPE'))}",
        f"   Forward P/E:         {_number(info.get('forwardPE'))}",
        (
            "   Price/Sales (TTM):   "
            f"{_number(info.get('priceToSalesTrailing12Months'))}"
        ),
        f"   Profit Margin:       {_ratio_percent(info.get('profitMargins'))}",
        f"   Operating Margin:    {_ratio_percent(info.get('operatingMargins'))}",
        f"   Return on Equity:    {_ratio_percent(info.get('returnOnEquity'))}",
        f"   Beta:                {_number(info.get('beta'), 3)}",
        "",
        f"4. FINANCIAL PERFORMANCE ({period_label})",
        f"   Revenue:             {_large_currency(revenue)}",
        f"   Operating Income:    {_large_currency(operating_income)}",
        f"   Net Income:          {_large_currency(net_income)}",
        f"   EBITDA:              {_large_currency(ebitda)}",
        f"   Diluted EPS:         {_currency(diluted_eps)}",
        f"   EBITDA / Net Income: {_ratio(ebitda, net_income)}",
        "",
        f"5. CASH FLOW ({period_label})",
        f"   Operating Cash Flow: {_large_currency(operating_cash)}",
        f"   Free Cash Flow:      {_large_currency(free_cash)}",
        f"   Capital Expenditure: {_large_currency(capital_expenditure)}",
    ]

    lines.extend(["", "6. SEC EDGAR EVIDENCE"])
    if sec_edgar.get("error"):
        lines.append(f"   Unavailable:          {sec_edgar['error']}")
    elif sec_edgar:
        sic = _text(sec_edgar.get("sic"))
        sic_description = _text(sec_edgar.get("sic_description"))
        lines.extend(
            [
                f"   Source:               {_text(sec_edgar.get('source'))}",
                f"   Entity:               {_text(sec_edgar.get('entity_name'))}",
                f"   CIK:                  {_text(sec_edgar.get('cik'))}",
                f"   SIC:                  {sic} — {sic_description}",
                "   Official Company Facts:",
            ]
        )
        fact_lines = _sec_fact_lines(_mapping(sec_edgar.get("official_company_facts")))
        lines.extend(fact_lines or ["      None available"])
        lines.append("   Recent Filings:")
        filing_lines = _sec_filing_lines(sec_edgar.get("recent_filings"))
        lines.extend(filing_lines or ["      None available"])
    else:
        lines.append("   No SEC EDGAR evidence collected.")

    lines.extend(
        [
            "",
            "7. DIVIDEND",
            f"   Dividend Yield:      {_ratio_percent(info.get('dividendYield'))}",
        ]
    )

    risk_issues = [
        _issue_message(issue)
        for issue in validation
        if isinstance(issue, Mapping)
        and issue.get("type")
        in {"consistency", "invalid_scale", "invalid_value", "scale_mismatch"}
    ]
    risks = _unique_text(
        reflection.get("weaknesses"),
        reflection.get("suspicious_values"),
        risk_issues,
    )
    lines.extend(["", "8. RISKS AND UNCERTAINTIES"])
    lines.extend(
        (f"   - {risk}" for risk in risks)
        if risks
        else ["   None identified in the available evidence."]
    )

    lines.extend(["", "9. DATA QUALITY"])
    quality_notes = [
        *(
            f"Evidence strength: {strength}"
            for strength in _unique_text(reflection.get("strengths"))
        ),
        *(_issue_text(issue) for issue in validation),
        *(f"Report validation: {_issue_text(issue)}" for issue in report_validation),
    ]
    lines.extend(
        (f"   - {note}" for note in quality_notes)
        if quality_notes
        else ["   No automated validation issues reported."]
    )

    missing_issues = [
        _issue_message(issue)
        for issue in validation
        if isinstance(issue, Mapping)
        and issue.get("type") in {"missing_data", "missing_metric"}
    ]
    missing = _unique_text(
        reflection.get("missing_information"),
        missing_issues,
    )
    lines.extend(["", "10. MISSING INFORMATION"])
    lines.extend((f"   - {item}" for item in missing) if missing else ["   None"])

    further_research = _unique_text(
        reflection.get("follow_up_questions"),
        plan.get("questions"),
    )
    lines.extend(["", "11. FURTHER RESEARCH"])
    lines.extend(
        (f"   - {item}" for item in further_research)
        if further_research
        else ["   None identified."]
    )
    lines.extend(["", "=" * 70, "END OF FINAL RESEARCH REPORT", "=" * 70])
    return "\n".join(lines)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sec_fact_lines(facts: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for name, raw_fact in facts.items():
        fact = _mapping(raw_fact)
        unit = _text(fact.get("unit"))
        value = _number(fact.get("value"))
        metadata = [
            f"FY {_text(fact.get('fiscal_year'))}",
            f"period {_text(fact.get('fiscal_period'))}",
            f"ended {_text(fact.get('period_end'))}",
            f"filed {_text(fact.get('filed'))}",
            f"form {_text(fact.get('form'))}",
            f"accession {_text(fact.get('accession'))}",
        ]
        lines.append(f"      {name}: {value} {unit} ({'; '.join(metadata)})")
    return lines


def _sec_filing_lines(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for raw_filing in value:
        filing = _mapping(raw_filing)
        if not filing:
            continue
        lines.append(
            "      - "
            f"{_text(filing.get('form'))} | "
            f"filed {_text(filing.get('filing_date'))} | "
            f"report {_text(filing.get('report_date'))} | "
            f"accession {_text(filing.get('accession'))} | "
            f"{_text(filing.get('filing_url'))}"
        )
    return lines


def _unique_text(*collections: object) -> list[str]:
    unique: list[str] = []
    for collection in collections:
        if not isinstance(collection, (list, tuple)):
            continue
        for item in collection:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if normalized and normalized not in unique:
                unique.append(normalized)
    return unique


def _issue_message(issue: object) -> str:
    if not isinstance(issue, Mapping):
        return str(issue)
    return str(issue.get("message") or issue.get("field") or "Unknown issue")


def _issue_text(issue: object) -> str:
    if not isinstance(issue, Mapping):
        return str(issue)
    field = issue.get("field", issue.get("tool", "general"))
    return f"{field}: {_issue_message(issue)}"


def _latest_period(*statements: Mapping[str, Any]) -> object | None:
    periods: list[object] = []
    for statement in statements:
        for row in statement.values():
            if isinstance(row, Mapping):
                periods.extend(row.keys())
    if not periods:
        return None

    def sort_key(period: object) -> tuple[int, str]:
        match = re.search(r"(?:19|20)\d{2}", str(period))
        return (int(match.group(0)) if match else -1, str(period))

    return max(periods, key=sort_key)


def _statement_value(
    statement: Mapping[str, Any],
    row_name: str,
    period: object | None,
) -> object | None:
    row = statement.get(row_name)
    if not isinstance(row, Mapping) or not row:
        return None
    if period in row:
        return row[period]
    return next(iter(row.values()))


def _period_label(period: object | None) -> str:
    if period is None:
        return "N/A"
    match = re.search(r"(?:19|20)\d{2}", str(period))
    return match.group(0) if match else str(period)


def _text(value: object) -> str:
    return str(value) if value not in (None, "") else "N/A"


def _numeric(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Number):
        return None
    return float(value)


def _number(value: object, decimals: int = 2) -> str:
    number = _numeric(value)
    return "N/A" if number is None else f"{number:,.{decimals}f}"


def _currency(value: object) -> str:
    number = _numeric(value)
    return "N/A" if number is None else f"${number:,.2f}"


def _large_currency(value: object) -> str:
    number = _numeric(value)
    if number is None:
        return "N/A"
    magnitude = abs(number)
    if magnitude >= 1_000_000_000_000:
        return f"${number / 1_000_000_000_000:.3f}T"
    if magnitude >= 1_000_000_000:
        return f"${number / 1_000_000_000:.3f}B"
    if magnitude >= 1_000_000:
        return f"${number / 1_000_000:.3f}M"
    return _currency(number)


def _percentage_points(value: object) -> str:
    number = _numeric(value)
    return "N/A" if number is None else f"{number:.2f}%"


def _ratio_percent(value: object) -> str:
    number = _numeric(value)
    return "N/A" if number is None else f"{number * 100:.2f}%"


def _ratio(numerator: object, denominator: object) -> str:
    first = _numeric(numerator)
    second = _numeric(denominator)
    if first is None or second in (None, 0):
        return "N/A"
    return f"{first / second:.3f}x"
