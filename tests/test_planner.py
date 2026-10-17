"""Tests for request-bounded research planning."""

import json

from src.agents.planner import PlannerAgent
from src.memory import ResearchMemoryStore


def test_planner_cannot_drop_tools_required_by_the_selected_route(tmp_path):
    response = json.dumps(
        {
            "objectives": ["Review all requested evidence"],
            "tools": ["price_data"],
            "questions": ["What affects current risk?"],
        }
    )
    planner = PlannerAgent(
        lambda _prompt: response,
        ResearchMemoryStore(tmp_path / "memory.json"),
    )
    available = [
        "price_data",
        "financials",
        "balance_sheet",
        "financial_growth",
        "sec_edgar",
    ]

    plan = planner.plan(
        "AAPL",
        available,
        "Compare market, financial, SEC, and news risk.",
        route="comprehensive",
        specialists=["market", "financial", "news"],
    )

    assert plan["tools"][0] == "price_data"
    assert set(plan["tools"]) == set(available)
