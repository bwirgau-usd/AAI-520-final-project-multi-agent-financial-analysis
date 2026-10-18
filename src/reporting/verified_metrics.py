"""Canonical financial values shared by generated and deterministic reports."""

from __future__ import annotations

import re
from collections.abc import Mapping
from numbers import Number
from typing import Any, TypedDict

_SCOPED_VERIFICATION_CLAIM = (
    "SEC facts provide primary-source evidence for selected financial metrics. "
    "Market data and news remain provider-supplied and require independent "
    "verification."
)


class VerifiedMetric(TypedDict):
    """One provider value with an explicit display unit."""

    label: str
    value: float
    formatted: str
    period: str | None
    unit: str


def verified_financial_metrics(
    observations: Mapping[str, Any],
) -> list[VerifiedMetric]:
    """Return exact report values derived without model arithmetic."""

    financials = _mapping(observations.get("financials"))
    cash_flow = _mapping(observations.get("cash_flow"))
    company = _mapping(observations.get("company_info"))
    price = _mapping(observations.get("price_data"))
    balance_sheet = _mapping(observations.get("balance_sheet"))
    balance_latest = _mapping(balance_sheet.get("latest"))
    balance_trends = _mapping(balance_sheet.get("trends"))
    growth = _mapping(observations.get("financial_growth"))
    metrics: list[VerifiedMetric] = []

    for label, key, source, formatter, unit in (
        ("Current Price", "currentPrice", company, _price, "USD/share"),
        ("Market Capitalization", "marketCap", company, _currency, "USD"),
        ("Enterprise Value", "enterpriseValue", company, _currency, "USD"),
        ("Start Price", "start_price", price, _price, "USD/share"),
        ("Latest Price", "latest_price", price, _price, "USD/share"),
        ("One-Month Return", "1m_return_percent", price, _percent, "percent"),
        ("Three-Month Return", "3m_return_percent", price, _percent, "percent"),
        ("One-Year Return", "1y_return_percent", price, _percent, "percent"),
        (
            "Annualized Volatility",
            "annualized_volatility_percent",
            price,
            _percent,
            "percent",
        ),
        (
            "Maximum Drawdown",
            "maximum_drawdown_percent",
            price,
            _percent,
            "percent",
        ),
        ("52-Week High", "52_week_high", price, _price, "USD/share"),
        ("52-Week Low", "52_week_low", price, _price, "USD/share"),
        ("Latest Volume", "latest_volume", price, _integer, "shares"),
        ("Average Volume", "average_volume", price, _integer, "shares"),
        ("Price Observation Count", "observations", price, _integer, "sessions"),
        ("Trailing P/E", "trailingPE", company, _multiple, "ratio"),
        ("Forward P/E", "forwardPE", company, _multiple, "ratio"),
        (
            "Price/Sales",
            "priceToSalesTrailing12Months",
            company,
            _multiple,
            "ratio",
        ),
        ("Profit Margin", "profitMargins", company, _ratio_percent, "percent"),
        (
            "Operating Margin",
            "operatingMargins",
            company,
            _ratio_percent,
            "percent",
        ),
        ("Return on Equity", "returnOnEquity", company, _ratio_percent, "percent"),
        ("Beta", "beta", company, _multiple, "ratio"),
    ):
        value = _number(source.get(key))
        if value is not None:
            metrics.append(
                {
                    "label": label,
                    "value": value,
                    "formatted": formatter(value),
                    "period": None,
                    "unit": unit,
                }
            )

    for label, row_name, source, formatter, unit in (
        ("Revenue", "Total Revenue", financials, _currency, "USD"),
        (
            "Operating Expenses",
            "Operating Expenses",
            financials,
            _currency,
            "USD",
        ),
        ("Operating Income", "Operating Income", financials, _currency, "USD"),
        ("Net Income", "Net Income", financials, _currency, "USD"),
        ("EBITDA", "EBITDA", financials, _currency, "USD"),
        ("Diluted EPS", "Diluted EPS", financials, _price, "USD/share"),
        (
            "Operating Cash Flow",
            "Operating Cash Flow",
            cash_flow,
            _currency,
            "USD",
        ),
        ("Free Cash Flow", "Free Cash Flow", cash_flow, _currency, "USD"),
        (
            "Capital Expenditure",
            "Capital Expenditure",
            cash_flow,
            _currency,
            "USD",
        ),
    ):
        period, value = _latest_statement_value(source, row_name)
        if value is not None:
            metrics.append(
                {
                    "label": label,
                    "value": value,
                    "formatted": formatter(value),
                    "period": period,
                    "unit": unit,
                }
            )

    _, ebitda = _latest_statement_value(financials, "EBITDA")
    ratio_period, net_income = _latest_statement_value(financials, "Net Income")
    if ebitda is not None and net_income not in (None, 0):
        ratio = ebitda / net_income
        metrics.append(
            {
                "label": "EBITDA / Net Income",
                "value": ratio,
                "formatted": f"{ratio:.3f}x",
                "period": ratio_period,
                "unit": "ratio",
            }
        )

    dividend_yield = _number(company.get("dividendYieldPercent"))
    if dividend_yield is None:
        dividend_yield = _number(company.get("dividendYield"))
    if dividend_yield is not None:
        metrics.append(
            {
                "label": "Dividend Yield",
                "value": dividend_yield,
                "formatted": f"{dividend_yield:.2f}%",
                "period": None,
                "unit": "percent",
            }
        )

    balance_period = _optional_period(balance_trends.get("latest_period"))
    for label, key, unit in (
        ("Cash and Short-Term Investments", "cash", "USD"),
        ("Total Debt", "debt", "USD"),
        ("Net Debt", "net_debt", "USD"),
        ("Total Assets", "total_assets", "USD"),
        ("Total Liabilities", "total_liabilities", "USD"),
        ("Stockholders' Equity", "stockholders_equity", "USD"),
    ):
        value = _number(balance_latest.get(key))
        if value is not None:
            metrics.append(
                {
                    "label": label,
                    "value": value,
                    "formatted": _currency(value),
                    "period": balance_period,
                    "unit": unit,
                }
            )
    cash_to_debt = _number(balance_latest.get("cash_to_debt_ratio"))
    if cash_to_debt is not None:
        metrics.append(
            {
                "label": "Cash / Debt",
                "value": cash_to_debt,
                "formatted": f"{cash_to_debt:.3f}x",
                "period": balance_period,
                "unit": "ratio",
            }
        )

    growth_period = _growth_period(growth)
    for label, key in (
        ("Revenue Growth", "revenue_growth_percent"),
        ("Net Income Growth", "net_income_growth_percent"),
        ("Diluted EPS Growth", "diluted_eps_growth_percent"),
    ):
        value = _number(growth.get(key))
        if value is not None:
            metrics.append(
                {
                    "label": label,
                    "value": value,
                    "formatted": f"{value:.2f}%",
                    "period": growth_period,
                    "unit": "percent change",
                }
            )

    trend_period = _growth_period(balance_trends)
    for label, key in (
        ("Cash Trend", "cash_growth_percent"),
        ("Debt Trend", "debt_growth_percent"),
        ("Assets Trend", "assets_growth_percent"),
        ("Liabilities Trend", "liabilities_growth_percent"),
        ("Equity Trend", "equity_growth_percent"),
    ):
        value = _number(balance_trends.get(key))
        if value is not None:
            metrics.append(
                {
                    "label": label,
                    "value": value,
                    "formatted": f"{value:.2f}%",
                    "period": trend_period,
                    "unit": "percent change",
                }
            )
    return metrics


def verified_metrics_markdown(observations: Mapping[str, Any]) -> str:
    """Render the canonical values as an auditable Markdown section."""

    metrics = verified_financial_metrics(observations)
    if not metrics:
        return ""
    lines = [
        "## Verified Financial Metrics",
        "",
        (
            "The following values are rendered deterministically from provider "
            "observations; no model arithmetic is used."
        ),
        "",
    ]
    for metric in metrics:
        period = f" ({metric['period']})" if metric["period"] else ""
        unit_note = (
            " (Yahoo Finance supplies this field in percentage points.)"
            if metric["label"] == "Dividend Yield"
            else ""
        )
        lines.append(
            f"- **{metric['label']}**{period}: {metric['formatted']}{unit_note}"
        )
    return "\n".join(lines)


def reconcile_report_financial_values(
    report: str,
    observations: Mapping[str, Any],
) -> str:
    """Replace model-authored financial figures with a canonical section."""

    report = _qualify_article_score_labels(_qualify_verification_claim(report))
    sec = _mapping(observations.get("sec_edgar"))
    if (
        sec.get("official_company_facts")
        and _SCOPED_VERIFICATION_CLAIM.casefold() not in report.casefold()
    ):
        report = (
            f"{report.rstrip()}\n\n## Verification Scope\n\n"
            f"{_SCOPED_VERIFICATION_CLAIM}"
        )
    metrics = verified_financial_metrics(observations)
    if not metrics:
        return report
    protected_labels = tuple(metric["label"].casefold() for metric in metrics)
    lines = report.splitlines()
    retained: list[str] = []
    skip_heading_value = False
    in_verified_section = False

    for line in lines:
        normalized = line.casefold().strip()
        if normalized.startswith("## verified financial metrics"):
            in_verified_section = True
            continue
        if in_verified_section:
            if normalized.startswith("## "):
                in_verified_section = False
            else:
                continue
        if skip_heading_value:
            if not normalized:
                continue
            skip_heading_value = False
            continue
        if any(label in normalized for label in protected_labels):
            skip_heading_value = normalized.startswith("#")
            continue
        retained.append(line)

    cleaned = "\n".join(retained).strip()
    verified = verified_metrics_markdown(observations)
    return f"{cleaned}\n\n{verified}" if cleaned else verified


def append_verified_interpretation(
    report: str,
    observations: Mapping[str, Any],
) -> str:
    """Append deterministic cross-domain reasoning to an optimized report."""

    price = _mapping(observations.get("price_data"))
    balance_sheet = _mapping(observations.get("balance_sheet"))
    balance = _mapping(balance_sheet.get("latest"))
    balance_trends = _mapping(balance_sheet.get("trends"))
    growth = _mapping(observations.get("financial_growth"))
    sec = _mapping(observations.get("sec_edgar"))
    news = _mapping(observations.get("news_analysis"))
    paragraphs: list[str] = []

    one_year = _number(price.get("1y_return_percent"))
    volatility = _number(price.get("annualized_volatility_percent"))
    drawdown = _number(price.get("maximum_drawdown_percent"))
    if one_year is not None and volatility is not None and drawdown is not None:
        paragraphs.append(
            "Because the one-year return was "
            f"{_percent(one_year)} while annualized volatility was "
            f"{_percent(volatility)} and maximum drawdown was "
            f"{_percent(drawdown)}, the historical return must be considered "
            "together with measured price risk; these observations do not "
            "predict future performance."
        )

    revenue_growth = _number(growth.get("revenue_growth_percent"))
    income_growth = _number(growth.get("net_income_growth_percent"))
    cash = _number(balance.get("cash"))
    debt = _number(balance.get("debt"))
    if any(
        value is not None
        for value in (revenue_growth, income_growth, cash, debt)
    ):
        growth_text = (
            f"Revenue growth of {_percent(revenue_growth)} and net-income "
            f"growth of {_percent(income_growth)} indicate the latest "
            "year-over-year statement changes. "
            if revenue_growth is not None and income_growth is not None
            else ""
        )
        balance_text = (
            f"Cash of {_currency(cash)} compared with total debt of "
            f"{_currency(debt)} shows the reported balance-sheet exposure; "
            if cash is not None and debt is not None
            else ""
        )
        paragraphs.append(
            f"{growth_text}{balance_text}however, these period snapshots alone "
            "do not establish future liquidity or earnings durability."
        )

    facts = sec.get("official_company_facts")
    filings = sec.get("recent_filings")
    fact_count = len(facts) if isinstance(facts, Mapping) else 0
    filing_count = len(filings) if isinstance(filings, list) else 0
    if fact_count or filing_count:
        paragraphs.append(
            f"SEC EDGAR supplied {fact_count} official company fact(s) and "
            f"{filing_count} recent filing record(s), providing primary-source "
            "corroboration; however, filing periods and provider statement "
            "periods should be compared explicitly before drawing conclusions."
        )

    yahoo_equity = _number(balance.get("stockholders_equity"))
    yahoo_period = _optional_period(balance_trends.get("latest_period"))
    sec_equity = _mapping(_mapping(facts).get("Stockholders Equity"))
    sec_equity_value = _number(sec_equity.get("value"))
    if yahoo_equity is not None and sec_equity_value is not None:
        sec_period_parts = [
            part
            for part in (
                (
                    f"fiscal {sec_equity.get('fiscal_year')}"
                    if sec_equity.get("fiscal_year") not in (None, "")
                    else ""
                ),
                str(sec_equity.get("fiscal_period") or ""),
                (
                    f"ended {sec_equity.get('period_end')}"
                    if sec_equity.get("period_end") not in (None, "")
                    else ""
                ),
            )
            if part
        ]
        yahoo_period_text = f" for {yahoo_period}" if yahoo_period else ""
        sec_period_text = (
            f" for {' '.join(sec_period_parts)}" if sec_period_parts else ""
        )
        paragraphs.append(
            "Yahoo Finance reports stockholders' equity of "
            f"{_currency(yahoo_equity)}{yahoo_period_text}, while SEC company "
            f"facts report {_currency(sec_equity_value)}{sec_period_text}. "
            "These values describe different reporting periods and provider "
            "snapshots and should not be treated as the same balance-sheet date."
        )

    article_count = _number(news.get("article_count"))
    average_structural_score = _number(
        news.get("average_structural_score", news.get("average_score"))
    )
    average_substantive_score = _number(
        news.get("average_substantive_reasoning_score")
    )
    if article_count is not None and article_count > 0:
        structural_text = (
            " The structural completeness and source-traceability rubric "
            f"averaged {_percent(average_structural_score)}."
            if average_structural_score is not None
            else ""
        )
        substantive_text = (
            " The separate substantive financial-reasoning and event-significance "
            f"score averaged {_percent(average_substantive_score)}."
            if average_substantive_score is not None
            else ""
        )
        paragraphs.append(
            f"The news workflow processed {_integer(article_count)} article(s)."
            f"{structural_text}{substantive_text} A 100% structural score means "
            "the expected fields and traceable source evidence were present; it "
            "does not establish perfect financial analysis. Because provider "
            "payloads may contain only headlines or snippets, detected events "
            "remain uncertain and should be verified at the linked publishers."
        )

    if not paragraphs:
        return report
    paragraphs.append(
        "Taken together, the market measurements, financial condition, SEC "
        "evidence, and current news indicate a mixed, evidence-bounded risk "
        "picture rather than a forecast or an investment recommendation."
    )
    cleaned = _remove_markdown_section(report, "evidence-based interpretation")
    section = "## Evidence-Based Interpretation\n\n" + "\n\n".join(paragraphs)
    return f"{cleaned.strip()}\n\n{section}" if cleaned.strip() else section


def financial_value_mismatches(
    report: str,
    observations: Mapping[str, Any],
) -> list[str]:
    """Identify canonical metrics absent from the complete report."""

    return [
        f"{metric['label']} must be reported as {metric['formatted']}."
        for metric in verified_financial_metrics(observations)
        if metric["formatted"] not in report
    ]


def _remove_markdown_section(report: str, heading: str) -> str:
    retained: list[str] = []
    skipping = False
    for line in report.splitlines():
        normalized = line.casefold().strip()
        if normalized.startswith(f"## {heading}"):
            skipping = True
            continue
        if skipping and normalized.startswith("## "):
            skipping = False
        if not skipping:
            retained.append(line)
    return "\n".join(retained)


def _qualify_verification_claim(report: str) -> str:
    """Replace an unsupported universal verification claim with scoped wording."""

    return re.sub(
        r"all data is verified with official company filings and primary sources\. ?",
        _SCOPED_VERIFICATION_CLAIM,
        report,
        flags=re.IGNORECASE,
    )


def _qualify_article_score_labels(report: str) -> str:
    """Make clear that article scores are structural, not overall quality grades."""

    report = re.sub(
        r"(?i)average evaluation score:",
        "Average Structural Completeness/Traceability Score:",
        report,
    )
    return re.sub(
        r"(?i)evaluator score:",
        "Structural Completeness/Traceability Score:",
        report,
    )


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _latest_statement_value(
    statement: Mapping[str, Any],
    row_name: str,
) -> tuple[str | None, float | None]:
    row = statement.get(row_name)
    if not isinstance(row, Mapping):
        return None, None
    for period, value in row.items():
        number = _number(value)
        if number is not None:
            return str(period), number
    return None, None


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Number):
        return None
    return float(value)


def _optional_period(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value).removesuffix(" 00:00:00")


def _growth_period(values: Mapping[str, Any]) -> str | None:
    latest = _optional_period(values.get("latest_period"))
    prior = _optional_period(values.get("prior_period"))
    if latest and prior:
        return f"{prior} to {latest}"
    return latest


def _currency(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def _price(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def _percent(value: float) -> str:
    return f"{value:.2f}%"


def _ratio_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _multiple(value: float) -> str:
    return f"{value:.3f}x"


def _integer(value: float) -> str:
    return f"{value:,.0f}"
