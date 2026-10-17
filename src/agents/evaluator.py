"""Deterministic and model-assisted research quality evaluation."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Mapping
from numbers import Number
from typing import Any

from src.llm import parse_json_object
from src.reporting.verified_metrics import (
    financial_value_mismatches,
    verified_financial_metrics,
)
from src.state import Reflection, ResearchPlan, ValidationIssue


class EvaluatorAgent:
    """Find data-quality issues and reflect on the evidence collected."""

    def __init__(self, llm: Callable[[str], str]) -> None:
        self._llm = llm

    def validate_observations(
        self,
        observations: Mapping[str, Any],
    ) -> list[ValidationIssue]:
        """Apply fast, reproducible checks before model interpretation."""

        issues: list[ValidationIssue] = []
        if not observations:
            return [
                {
                    "type": "missing_data",
                    "message": "No research tools produced observations.",
                }
            ]

        for tool_name, result in observations.items():
            if result is None or result == {}:
                issues.append(
                    {
                        "type": "missing_data",
                        "tool": tool_name,
                        "message": "Tool returned no usable data.",
                    }
                )
            elif isinstance(result, Mapping) and result.get("error"):
                issues.append(
                    {
                        "type": "tool_error",
                        "tool": tool_name,
                        "message": str(result["error"]),
                    }
                )

        news_analysis = observations.get("news_analysis")
        if (
            isinstance(news_analysis, Mapping)
            and not news_analysis.get("error")
            and news_analysis.get("article_count") == 0
        ):
            issues.append(
                {
                    "type": "missing_data",
                    "tool": "news_analysis",
                    "message": "No current company news articles were available.",
                }
            )

        price_data = observations.get("price_data")
        if isinstance(price_data, Mapping) and not price_data.get("error"):
            self._validate_price_data(price_data, issues)

        company_info = observations.get("company_info")
        financials = observations.get("financials")
        if isinstance(company_info, Mapping) and isinstance(financials, Mapping):
            market_cap = _finite_number(
                _find_value(
                    company_info,
                    {"market_cap", "marketCap", "marketCapitalization"},
                )
            )
            revenue = _latest_number(
                _find_value(
                    financials,
                    {"total_revenue", "totalRevenue", "revenue", "Total Revenue"},
                )
            )
            if market_cap is not None and revenue not in (None, 0):
                ratio = abs(market_cap / revenue)
                if ratio > 1_000:
                    issues.append(
                        {
                            "type": "scale_mismatch",
                            "field": "marketCap / Total Revenue",
                            "value": ratio,
                            "message": (
                                "Market capitalization and revenue may use "
                                "different units."
                            ),
                        }
                    )

        cash_flow = observations.get("cash_flow")
        if isinstance(cash_flow, Mapping) and not cash_flow.get("error"):
            operating_cash_value = _find_value(
                cash_flow,
                {
                    "operating_cash_flow",
                    "operatingCashFlow",
                    "operating_cashflow",
                    "Operating Cash Flow",
                },
            )
            free_cash_value = _find_value(
                cash_flow,
                {"free_cash_flow", "freeCashFlow", "Free Cash Flow"},
            )
            operating_cash = _latest_number(operating_cash_value)
            free_cash = _latest_number(free_cash_value)
            if operating_cash is not None and free_cash is None:
                issues.append(
                    {
                        "type": "missing_data",
                        "field": "free_cash_flow",
                        "message": (
                            "Operating cash flow exists, but free cash flow is "
                            "not available."
                        ),
                    }
                )
            if (
                operating_cash is not None
                and free_cash is not None
                and free_cash > operating_cash >= 0
            ):
                issues.append(
                    {
                        "type": "consistency",
                        "field": "Free Cash Flow",
                        "message": (
                            "Free cash flow exceeds operating cash flow; verify "
                            "the source periods and capital-expenditure sign."
                        ),
                    }
                )

        if isinstance(company_info, Mapping) and not company_info.get("error"):
            percentage_value = _finite_number(
                _find_value(
                    company_info,
                    {
                        "profit_margin",
                        "operating_margin",
                        "dividend_yield",
                        "profitMargins",
                        "operatingMargins",
                        "dividendYield",
                    },
                )
            )
            if percentage_value is not None and abs(percentage_value) > 1_000:
                issues.append(
                    {
                        "type": "invalid_scale",
                        "field": "company_percentage",
                        "value": percentage_value,
                        "message": (
                            "A percentage-like company value has an implausible scale."
                        ),
                    }
                )

        return issues

    def reflect(
        self,
        symbol: str,
        plan: ResearchPlan,
        observations: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> Reflection:
        """Use the model to assess coverage while retaining validation facts."""

        prompt = f"""
Act as a research quality reviewer for {symbol}. Evaluate only the evidence
provided. Do not invent facts or give personalized investment advice.

Plan:
{json.dumps(plan, default=str)}

Observations:
{json.dumps(observations, default=str)}

Deterministic validation issues:
{json.dumps(issues, default=str)}

Return only a JSON object with string arrays named strengths, weaknesses,
missing_information, suspicious_values, and follow_up_questions.
""".strip()
        fallback = {
            "strengths": [],
            "weaknesses": [],
            "missing_information": [],
            "suspicious_values": [],
            "follow_up_questions": [],
        }
        parsed = parse_json_object(self._llm(prompt), fallback=fallback)
        reflection: Reflection = {
            "strengths": _string_list(parsed.get("strengths")),
            "weaknesses": _string_list(parsed.get("weaknesses")),
            "missing_information": _string_list(parsed.get("missing_information")),
            "suspicious_values": _string_list(parsed.get("suspicious_values")),
            "follow_up_questions": _string_list(parsed.get("follow_up_questions")),
            "deterministic_issues": list(issues),
        }
        for issue in issues:
            issue_type = issue.get("type", "")
            message = issue.get("message", "")
            if not message:
                continue
            if issue_type in {"missing_data", "missing_metric"}:
                target = reflection["missing_information"]
            elif issue_type in {
                "consistency",
                "invalid_scale",
                "invalid_value",
                "scale_mismatch",
            }:
                target = reflection["suspicious_values"]
            else:
                target = reflection["weaknesses"]
            if message not in target:
                target.append(message)
        return reflection

    def validate_report(
        self,
        report: str,
        observations: Mapping[str, Any],
    ) -> list[ValidationIssue]:
        """Check the final prose for obvious completeness and safety problems."""

        issues: list[ValidationIssue] = []
        normalized_report = report.strip()
        if not normalized_report:
            return [
                {
                    "type": "empty_report",
                    "message": "The synthesis agent returned an empty report.",
                }
            ]

        incomplete_disclaimers = (
            "not intended to be a complete",
            "not intended to be complete",
            "not intended to be a comprehensive",
            "not intended to be comprehensive",
            "not a complete analysis",
            "not a comprehensive analysis",
            "may not be complete",
            "may not be comprehensive",
        )
        matched_disclaimer = next(
            (
                phrase
                for phrase in incomplete_disclaimers
                if phrase in normalized_report.casefold()
            ),
            None,
        )
        if matched_disclaimer:
            issues.append(
                {
                    "type": "incomplete_report_claim",
                    "value": matched_disclaimer,
                    "message": (
                        "The report disclaims completeness even though the workflow "
                        "requires a complete response to the research request."
                    ),
                }
            )

        if (
            "all data is verified with official company filings and primary sources"
            in normalized_report.casefold()
        ):
            issues.append(
                {
                    "type": "overstated_verification_claim",
                    "message": (
                        "The report overstates verification. SEC facts verify selected "
                        "financial metrics, while market and news data remain "
                        "provider-supplied."
                    ),
                }
            )

        cash_flow = observations.get("cash_flow")
        has_cash_data = (
            _find_value(
                cash_flow,
                {
                    "operating_cash_flow",
                    "operatingCashFlow",
                    "Operating Cash Flow",
                    "free_cash_flow",
                    "freeCashFlow",
                    "Free Cash Flow",
                },
            )
            is not None
        )
        false_missing_phrases = (
            "cash generation data is missing",
            "cash flow data is missing",
            "cash generation is missing",
        )
        if has_cash_data and any(
            phrase in report.lower() for phrase in false_missing_phrases
        ):
            issues.append(
                {
                    "type": "false_missing_claim",
                    "field": "cash_flow",
                    "message": (
                        "The report incorrectly claims cash-flow data is missing."
                    ),
                }
            )

        sec_data = observations.get("sec_edgar")
        if (
            isinstance(sec_data, Mapping)
            and not sec_data.get("error")
            and (
                sec_data.get("official_company_facts") or sec_data.get("recent_filings")
            )
            and "sec" not in report.lower()
            and "filing" not in report.lower()
        ):
            issues.append(
                {
                    "type": "missing_coverage",
                    "field": "sec_edgar",
                    "message": "The report does not discuss available SEC evidence.",
                }
            )

        news_data = observations.get("news_analysis")
        if (
            isinstance(news_data, Mapping)
            and news_data.get("article_count", 0)
            and "news" not in report.lower()
            and "catalyst" not in report.lower()
        ):
            issues.append(
                {
                    "type": "missing_coverage",
                    "field": "news_analysis",
                    "message": "The report does not discuss available news evidence.",
                }
            )

        prohibited_phrases = (
            "you should buy",
            "you should sell",
            "buy the stock",
            "sell the stock",
            "strong buy",
            "strong sell",
            "guaranteed return",
            "risk-free",
        )
        matched = next(
            (phrase for phrase in prohibited_phrases if phrase in report.lower()),
            None,
        )
        if matched:
            issues.append(
                {
                    "type": "unsafe_language",
                    "value": matched,
                    "message": (
                        "The report contains prescriptive or misleading language."
                    ),
                }
            )
        for mismatch in financial_value_mismatches(report, observations):
            issues.append(
                {
                    "type": "financial_mismatch",
                    "message": mismatch,
                }
            )
        for label, search_terms in _required_report_content(observations):
            if not any(term in normalized_report.casefold() for term in search_terms):
                issues.append(
                    {
                        "type": "missing_required_content",
                        "field": label,
                        "message": f"The report omits available {label} evidence.",
                    }
                )
        return issues

    def evaluate_report(
        self,
        report: str,
        observations: Mapping[str, Any],
        research_request: str,
        route: str,
        *,
        threshold: float = 75,
    ) -> dict[str, Any]:
        """Score the complete report with a transparent six-part rubric."""

        report_issues = self.validate_report(report, observations)
        text = report.lower()
        required_content = _required_report_content(observations, route=route)
        covered = sum(
            any(term in text for term in search_terms)
            for _, search_terms in required_content
        )
        completeness = round(100 * covered / max(len(required_content), 1))

        number_count = len(re.findall(r"(?<!\w)[+-]?\d+(?:\.\d+)?%?", report))
        evidence_terms = sum(
            term in text
            for term in ("observation", "reported", "according", "evidence", "source")
        )
        grounding = min(100, number_count * 10 + evidence_terms * 15)
        issue_types = {str(issue.get("type")) for issue in report_issues}
        if "financial_mismatch" in issue_types:
            grounding = min(grounding, 20)
        elif "missing_required_content" in issue_types:
            grounding = min(grounding, 50)

        reasoning_markers = sum(
            marker in text
            for marker in (
                "because",
                "therefore",
                "suggests",
                "indicates",
                "however",
                "while",
                "risk",
                "uncertainty",
            )
        )
        reasoning = min(100, reasoning_markers * 15)
        consistency = max(0, 100 - 25 * len(report_issues))
        if "financial_mismatch" in issue_types:
            consistency = 0

        source_markers = sum(
            marker in text
            for marker in (
                "yahoo",
                "sec",
                "newsapi",
                "google news",
                "http://",
                "https://",
                "source",
            )
        )
        sources = min(100, source_markers * 20)
        atx_headings = len(re.findall(r"(?m)^#{1,6}\s+", report))
        setext_headings = len(
            re.findall(r"(?m)^\S[^\n]*\n(?:=+|-+)\s*$", report)
        )
        headings = atx_headings + setext_headings
        clarity = min(100, (40 if len(report.split()) >= 80 else 20) + headings * 15)

        criteria = {
            "completeness": float(completeness),
            "grounding": float(grounding),
            "reasoning": float(reasoning),
            "consistency": float(consistency),
            "sources": float(sources),
            "clarity": float(clarity),
        }
        score = round(sum(criteria.values()) / len(criteria), 2)
        minimum_criterion_score = 60.0
        feedback = [
            f"Improve {name.replace('_', ' ')}; current score is {value:.0f}/100."
            for name, value in criteria.items()
            if value < 75
        ]
        if not _request_addressed(text, research_request):
            feedback.append("Answer the user's research request explicitly.")
        below_floor = [
            name for name, value in criteria.items() if value < minimum_criterion_score
        ]
        if below_floor:
            feedback.append(
                "No report can pass while these criteria are below "
                f"{minimum_criterion_score:.0f}/100: {', '.join(below_floor)}."
            )
        feedback.extend(str(issue.get("message", "")) for issue in report_issues)
        return {
            "score": score,
            "passed": (
                score >= threshold
                and not report_issues
                and not below_floor
            ),
            "threshold": threshold,
            "minimum_criterion_score": minimum_criterion_score,
            "criteria": criteria,
            "feedback": [item for item in feedback if item],
            "validation_issues": report_issues,
        }

    @staticmethod
    def _validate_price_data(
        price_data: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        fields = {
            "latest_price": {
                "latest_price",
                "current_price",
                "currentPrice",
                "regularMarketPrice",
                "price",
                "Current Price",
            },
            "1y_return_percent": {
                "one_year_return",
                "one_year_return_pct",
                "1y_return",
                "1y_return_percent",
                "return_1y",
            },
        }
        values = {
            field: _finite_number(_find_value(price_data, keys))
            for field, keys in fields.items()
        }
        for field, value in values.items():
            if value is None:
                issues.append(
                    {
                        "type": "missing_metric",
                        "tool": "price_data",
                        "field": field,
                        "message": f"Price data is missing {field}.",
                    }
                )

        latest_price = values["latest_price"]
        if latest_price is not None and latest_price <= 0:
            issues.append(
                {
                    "type": "invalid_value",
                    "tool": "price_data",
                    "field": "latest_price",
                    "value": latest_price,
                    "message": "Latest price must be positive.",
                }
            )

        for field, value in price_data.items():
            if "percent" not in field.lower():
                continue
            number = _finite_number(value)
            if number is not None and abs(number) > 1_000:
                issues.append(
                    {
                        "type": "invalid_scale",
                        "tool": "price_data",
                        "field": field,
                        "value": number,
                        "message": f"{field} has an implausible percentage scale.",
                    }
                )


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Number):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _find_value(value: object, keys: set[str]) -> object | None:
    if isinstance(value, Mapping):
        for key in keys:
            if key in value:
                return value[key]
        for item in value.values():
            found = _find_value(item, keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_value(item, keys)
            if found is not None:
                return found
    return None


def _latest_number(value: object) -> float | None:
    if isinstance(value, Mapping):
        for item in value.values():
            number = _finite_number(item)
            if number is not None:
                return number
        return None
    return _finite_number(value)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _required_report_content(
    observations: Mapping[str, Any],
    *,
    route: str = "comprehensive",
) -> list[tuple[str, tuple[str, ...]]]:
    """Describe visible evidence that a complete report must acknowledge."""

    requirements: list[tuple[str, tuple[str, ...]]] = []

    def add(label: str, value: object, *terms: str) -> None:
        if _has_usable_value(value):
            requirements.append((label, tuple(term.casefold() for term in terms)))

    include_market = route in {"market", "comprehensive"}
    include_financial = route in {"financial", "comprehensive"}
    include_news = route in {"news", "comprehensive"}
    price = observations.get("price_data")
    if include_market and isinstance(price, Mapping) and not price.get("error"):
        for label, key, terms in (
            ("latest price", "latest_price", ("latest price", "current price")),
            (
                "one-month return",
                "1m_return_percent",
                ("one-month", "1-month", "1m return"),
            ),
            (
                "three-month return",
                "3m_return_percent",
                ("three-month", "3-month", "3m return"),
            ),
            (
                "one-year return",
                "1y_return_percent",
                ("one-year", "1-year", "1y return"),
            ),
            ("volatility", "annualized_volatility_percent", ("volatility",)),
            ("maximum drawdown", "maximum_drawdown_percent", ("drawdown",)),
            ("52-week high", "52_week_high", ("52-week high", "52 week high")),
            ("52-week low", "52_week_low", ("52-week low", "52 week low")),
            ("latest volume", "latest_volume", ("latest volume", "trading volume")),
            ("average volume", "average_volume", ("average volume",)),
        ):
            add(label, price.get(key), *terms)

    if include_financial:
        for metric in verified_financial_metrics(observations):
            label = metric["label"].casefold()
            add(metric["label"], metric["value"], label)

        sec_data = observations.get("sec_edgar")
        if isinstance(sec_data, Mapping) and not sec_data.get("error"):
            add(
                "SEC EDGAR",
                sec_data.get("official_company_facts")
                or sec_data.get("recent_filings"),
                "sec",
                "filing",
            )

    news = observations.get("news_analysis")
    if include_news and isinstance(news, Mapping) and not news.get("error"):
        add("news", news.get("article_count"), "news", "headline", "catalyst")

    if requirements:
        return list(dict.fromkeys(requirements))
    fallback_terms = {
        "market": [("market analysis", ("price", "return", "market"))],
        "financial": [("financial analysis", ("revenue", "income", "financial"))],
        "news": [("news analysis", ("news", "headline", "event"))],
        "comprehensive": [
            ("market analysis", ("price", "return", "market")),
            ("financial analysis", ("revenue", "income", "financial")),
            ("news analysis", ("news", "headline", "event")),
        ],
    }
    return fallback_terms.get(route, fallback_terms["comprehensive"])


def _has_usable_value(value: object) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, Mapping):
        return bool(value) and not value.get("error")
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    return True


def _request_addressed(report_text: str, research_request: str) -> bool:
    """Check request coverage without requiring verbatim question repetition."""

    if not research_request.strip():
        return True
    stopwords = {
        "affect",
        "and",
        "company",
        "current",
        "does",
        "how",
        "the",
        "their",
        "this",
        "what",
    }
    request_terms = {
        term
        for term in re.findall(r"[a-z0-9]+", research_request.casefold())
        if len(term) >= 3 and term not in stopwords
    }
    if not request_terms:
        return True
    covered = sum(term in report_text for term in request_terms)
    return covered / len(request_terms) >= 0.6
