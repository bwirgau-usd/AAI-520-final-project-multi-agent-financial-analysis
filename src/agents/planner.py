"""Agent responsible for planning investment research tasks."""

from __future__ import annotations

import json
from collections.abc import Callable, Collection, Mapping
from typing import Any

from src.llm import parse_json_object
from src.memory import ResearchMemoryStore
from src.state import ResearchPlan

DEFAULT_OBJECTIVES = [
    "Assess recent price performance and risk",
    "Review company profile and valuation",
    "Review earnings and cash-flow trends",
    "Verify official SEC facts and recent filings",
    "Assess current company news, catalysts, and uncertainty",
]


class PlannerAgent:
    """Create a bounded research plan using current tools and prior memories."""

    def __init__(
        self,
        llm: Callable[[str], str],
        memory_store: ResearchMemoryStore,
    ) -> None:
        self._llm = llm
        self._memory_store = memory_store

    def plan(
        self,
        symbol: str,
        available_tools: Collection[str],
        research_request: str | None = None,
        *,
        route: str = "comprehensive",
        specialists: Collection[str] = (),
    ) -> ResearchPlan:
        """Ask the model for a plan and restrict it to registered tools."""

        normalized_symbol = symbol.strip().upper()
        request = (research_request or "Provide a comprehensive investment research report.").strip()
        tool_names = sorted(set(available_tools))
        memories = self._memory_store.for_symbol(normalized_symbol)[-3:]
        required_tools = _minimum_required_tools(request, route, tool_names)
        available_optional_tools = [
            name for name in tool_names if name not in required_tools
        ]
        memory_actions = _memory_actions(memories)
        fallback: ResearchPlan = {
            "objectives": list(DEFAULT_OBJECTIVES),
            "tools": list(required_tools),
            "required_tools": list(required_tools),
            "optional_tools": [],
            "available_optional_tools": available_optional_tools,
            "questions": [
                "What are the strongest signals in the available evidence?",
                "Which risks or data gaps could change the interpretation?",
                "What do official SEC facts and recent filings show?",
                "What material developments appear in current company news?",
            ],
            "research_request": request,
            "route": route,
            "specialists": list(specialists),
            "memory_context": memories,
            "applied_memory_actions": memory_actions,
        }
        prompt = f"""
You are planning an evidence-based investment research workflow for
{normalized_symbol}. Available tools: {json.dumps(tool_names)}.
User research request: {request}
Selected route: {route}. Selected specialists: {json.dumps(list(specialists))}.
Relevant notes from previous runs: {json.dumps(memories, default=str)}.

Minimum required tools: {json.dumps(required_tools)}.
Optional tools available for selection: {json.dumps(available_optional_tools)}.

Return only one JSON object with string arrays named objectives, tools, and
questions, plus a tool_reasons object mapping each selected optional tool to a
short reason. Always retain the minimum required tools. Select an optional tool
only when it supplies evidence needed by the request or a saved next-run action.
Use prior notes as planning context, never as current market evidence.
""".strip()

        parsed = parse_json_object(self._llm(prompt), fallback=fallback)
        selected_tools = [
            item for item in _string_list(parsed.get("tools")) if item in tool_names
        ]
        final_tools = [
            *required_tools,
            *(name for name in selected_tools if name not in required_tools),
        ]
        selected_optional = [
            name for name in final_tools if name not in required_tools
        ]
        tool_reasons = parsed.get("tool_reasons", {})
        reason_mapping = tool_reasons if isinstance(tool_reasons, Mapping) else {}
        optional_tools = [
            {
                "name": name,
                "reason": _optional_tool_reason(
                    name,
                    request,
                    reason_mapping.get(name),
                ),
            }
            for name in selected_optional
        ]
        questions = _string_list(parsed.get("questions")) or fallback["questions"]
        if _memory_calls_for_source_traceability(memories) and not any(
            "filing-level citation" in question.casefold()
            or "provider source url" in question.casefold()
            for question in questions
        ):
            questions.append(
                "Which material claims can be linked to filing-level citations "
                "or provider source URLs?"
            )
        objectives = _string_list(parsed.get("objectives")) or fallback["objectives"]
        for lesson in memory_actions:
            action = lesson["next_run_action"]
            objective = f"Apply prior-run feedback: {action}"
            if objective not in objectives:
                objectives.append(objective)
            success_question = (
                "How does this run satisfy the saved success check: "
                f"{lesson['success_check']}?"
            )
            if success_question not in questions:
                questions.append(success_question)
        return {
            "objectives": objectives,
            "tools": final_tools,
            "required_tools": required_tools,
            "optional_tools": optional_tools,
            "available_optional_tools": available_optional_tools,
            "questions": questions,
            "research_request": request,
            "route": route,
            "specialists": list(specialists),
            "memory_context": memories,
            "applied_memory_actions": memory_actions,
        }


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _memory_calls_for_source_traceability(
    memories: list[dict[str, object]],
) -> bool:
    """Return whether saved feedback explicitly requests stronger sourcing."""

    memory_text = json.dumps(memories, default=str).casefold().replace("-", " ")
    return bool(memories) and any(
        marker in memory_text
        for marker in (
            "source traceability",
            "primary source",
            "filing citation",
            "filing-level citation",
            "source link",
            "linked source",
            "citation",
        )
    )


def _memory_actions(memories: list[dict[str, object]]) -> list[dict[str, str]]:
    """Return unique, fully structured actions saved by prior runs."""

    actions: list[dict[str, str]] = []
    seen: set[str] = set()
    for memory in memories:
        lessons = memory.get("lessons", [])
        if not isinstance(lessons, list):
            continue
        for item in lessons:
            if not isinstance(item, Mapping):
                continue
            lesson = {
                key: str(item.get(key) or "").strip()
                for key in ("weakness", "next_run_action", "success_check")
            }
            action_key = lesson["next_run_action"].casefold()
            if all(lesson.values()) and action_key not in seen:
                actions.append(lesson)
                seen.add(action_key)
    return actions


def _minimum_required_tools(
    request: str,
    route: str,
    available_tools: list[str],
) -> list[str]:
    """Select only the evidence floor required by the routed request."""

    normalized = request.casefold()
    candidates: list[str] = []
    if route in {"market", "comprehensive"}:
        candidates.append("price_data")
        if any(term in normalized for term in ("profile", "market cap", "beta")):
            candidates.append("company_info")

    if route in {"financial", "comprehensive"}:
        requested_financial_tools = {
            "financials": (
                "revenue",
                "earnings",
                "income",
                "expense",
                "profit",
                "margin",
            ),
            "cash_flow": ("cash flow", "free cash", "capital expenditure"),
            "balance_sheet": ("balance sheet", "liquidity", "cash", "debt"),
            "financial_growth": ("growth", "trend"),
            "sec_edgar": ("sec", "filing", "10-k", "10-q", "8-k"),
            "company_info": ("valuation", "company profile", "dividend"),
        }
        matched = False
        for tool, terms in requested_financial_tools.items():
            if any(term in normalized for term in terms):
                candidates.append(tool)
                matched = True
        if route == "comprehensive" or not matched:
            candidates.append("financials")

    registered = set(available_tools)
    return [
        name for name in dict.fromkeys(candidates) if name in registered
    ]


def _optional_tool_reason(
    tool_name: str,
    request: str,
    model_reason: Any,
) -> str:
    reason = str(model_reason or "").strip()
    if reason:
        return reason
    labels = {
        "company_info": "Adds company profile and valuation context",
        "financials": "Adds income-statement evidence",
        "cash_flow": "Adds cash-generation and capital-spending evidence",
        "balance_sheet": "Adds liquidity, cash, and debt evidence",
        "financial_growth": "Adds deterministic revenue and earnings growth",
        "sec_edgar": "Adds primary-source facts and filing links",
        "price_data": "Adds return, volatility, drawdown, and volume evidence",
    }
    return f"{labels.get(tool_name, 'Adds relevant evidence')} for: {request}"
