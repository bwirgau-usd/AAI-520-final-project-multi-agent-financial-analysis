"""Agent responsible for planning investment research tasks."""

from __future__ import annotations

import json
from collections.abc import Callable, Collection

from src.llm import parse_json_object
from src.memory import ResearchMemoryStore
from src.state import ResearchPlan


DEFAULT_OBJECTIVES = [
    "Assess recent price performance and risk",
    "Review company profile and valuation",
    "Review earnings and cash-flow trends",
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
    ) -> ResearchPlan:
        """Ask the model for a plan and restrict it to registered tools."""

        normalized_symbol = symbol.strip().upper()
        tool_names = sorted(set(available_tools))
        fallback: ResearchPlan = {
            "objectives": list(DEFAULT_OBJECTIVES),
            "tools": list(tool_names),
            "questions": [
                "What are the strongest signals in the available evidence?",
                "Which risks or data gaps could change the interpretation?",
            ],
        }
        memories = self._memory_store.for_symbol(normalized_symbol)[-3:]
        prompt = f"""
You are planning an evidence-based investment research workflow for
{normalized_symbol}. Available tools: {json.dumps(tool_names)}.
Relevant notes from previous runs: {json.dumps(memories, default=str)}.

Return only one JSON object with string arrays named objectives, tools, and
questions. Select only tools from the available list. Use prior notes as
planning context, never as current market evidence.
""".strip()

        parsed = parse_json_object(self._llm(prompt), fallback=fallback)
        selected_tools = [
            item
            for item in _string_list(parsed.get("tools"))
            if item in tool_names
        ]
        return {
            "objectives": _string_list(parsed.get("objectives"))
            or fallback["objectives"],
            "tools": selected_tools or fallback["tools"],
            "questions": _string_list(parsed.get("questions"))
            or fallback["questions"],
        }


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
