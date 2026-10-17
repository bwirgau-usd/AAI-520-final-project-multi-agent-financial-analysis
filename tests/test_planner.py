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


def test_source_traceability_memory_adds_a_specific_follow_up_question(tmp_path):
    store = ResearchMemoryStore(tmp_path / "memory.json")
    planner = PlannerAgent(
        lambda _prompt: json.dumps(
            {
                "objectives": ["Review current evidence"],
                "tools": ["sec_edgar"],
                "questions": ["What do recent filings show?"],
            }
        ),
        store,
    )

    first = planner.plan("AAPL", ["sec_edgar"])
    store.add(
        "AAPL",
        "Run 1 feedback says to verify linked sources for news articles.",
    )
    second = planner.plan("AAPL", ["sec_edgar"])

    learned_question = (
        "Which material claims can be linked to filing-level citations or "
        "provider source URLs?"
    )
    assert learned_question not in first["questions"]
    assert learned_question in second["questions"]
    assert second["memory_context"]
