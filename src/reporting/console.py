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
    validation = state.get("validation", [])
    period = _latest_period(financials, cash_flow)
    period_label = _period_label(period)

    current_price = price.get("latest_price", info.get("currentPrice"))
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
        f"   One-Year Return:     {_percentage_points(price.get('1y_return_percent'))}",
        (
            "   Annualized Volatility: "
            f"{_percentage_points(price.get('annualized_volatility_percent'))}"
        ),
        (
            "   Maximum Drawdown:    "
            f"{_percentage_points(price.get('maximum_drawdown_percent'))}"
        ),
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
        "",
        "6. DIVIDEND",
        f"   Dividend Yield:      {_ratio_percent(info.get('dividendYield'))}",
        "",
        "7. DATA VALIDATION",
    ]
    if validation:
        lines.extend(
            f"   - {issue.get('field', issue.get('tool', 'general'))}: "
            f"{issue.get('message', str(issue))}"
            for issue in validation
        )
    else:
        lines.append("   No validation issues reported.")

    missing = [
        issue.get("field", issue.get("tool", "unknown"))
        for issue in validation
        if issue.get("type") in {"missing_data", "missing_metric"}
    ]
    lines.extend(["", "8. MISSING INFORMATION"])
    lines.extend((f"   - {field}" for field in missing) if missing else ["   None"])
    lines.extend(["", "=" * 70, "END OF FINAL RESEARCH REPORT", "=" * 70])
    return "\n".join(lines)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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
