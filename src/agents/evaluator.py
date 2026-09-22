"""Deterministic and model-assisted research quality evaluation."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from numbers import Number
from typing import Any

from src.llm import parse_json_object
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
                and free_cash > operating_cash
                and operating_cash >= 0
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
                            "A percentage-like company value has an implausible "
                            "scale."
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
            "missing_information": _string_list(
                parsed.get("missing_information")
            ),
            "suspicious_values": _string_list(parsed.get("suspicious_values")),
            "follow_up_questions": _string_list(
                parsed.get("follow_up_questions")
            ),
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

        cash_flow = observations.get("cash_flow")
        has_cash_data = _find_value(
            cash_flow,
            {
                "operating_cash_flow",
                "operatingCashFlow",
                "Operating Cash Flow",
                "free_cash_flow",
                "freeCashFlow",
                "Free Cash Flow",
            },
        ) is not None
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
        return issues

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
