"""Safe execution boundary for planner-selected research tools."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from src.state import ResearchPlan
from src.tools.registry import Tool


def execute_tools(
    symbol: str,
    plan: ResearchPlan,
    tools: Mapping[str, Tool],
    *,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Execute allow-listed tools and capture failures as observations."""

    observations: dict[str, Any] = {}
    for tool_name in plan["tools"]:
        if progress is not None:
            progress(f"Running tool: {tool_name}")
        tool = tools.get(tool_name)
        if tool is None:
            observations[tool_name] = {"error": "Tool is not registered"}
            continue
        try:
            result = tool(symbol)
        except Exception as exc:  # keep one provider failure from ending the run
            observations[tool_name] = {
                "error": f"{type(exc).__name__}: {exc}"
            }
            continue
        observations[tool_name] = (
            result if result is not None else {"error": "Tool returned no data"}
        )
    return observations
