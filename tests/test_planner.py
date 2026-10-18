"""Tests for request-bounded research planning."""

import json

from src.agents.planner import PlannerAgent
from src.memory import ResearchMemoryStore


def test_planner_keeps_required_tools_without_forcing_all_route_tools(tmp_path):
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
    assert set(plan["tools"]) == {"price_data", "financials", "sec_edgar"}
    assert plan["required_tools"] == ["price_data", "sec_edgar", "financials"]
    assert plan["optional_tools"] == []
    assert set(plan["available_optional_tools"]) == {
        "balance_sheet",
        "financial_growth",
    }


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


def test_planner_selects_different_optional_tools_for_different_questions(tmp_path):
    responses = {
        "volatility": {
            "objectives": ["Measure market risk"],
            "tools": ["price_data"],
            "questions": ["How volatile is the price?"],
            "tool_reasons": {},
        },
        "liquidity": {
            "objectives": ["Assess liquidity"],
            "tools": ["balance_sheet", "cash_flow"],
            "questions": ["Can cash cover debt and spending?"],
            "tool_reasons": {
                "cash_flow": "Checks whether operations replenish liquidity",
            },
        },
    }

    def llm(prompt):
        key = "volatility" if "price volatility" in prompt else "liquidity"
        return json.dumps(responses[key])

    planner = PlannerAgent(llm, ResearchMemoryStore(tmp_path / "memory.json"))
    tools = ["price_data", "company_info", "financials", "cash_flow", "balance_sheet"]

    market = planner.plan(
        "AAPL", tools, "Analyze price volatility", route="market"
    )
    liquidity = planner.plan(
        "AAPL",
        tools,
        "Assess liquidity and debt",
        route="financial",
    )

    assert market["tools"] == ["price_data"]
    assert market["optional_tools"] == []
    assert liquidity["required_tools"] == ["balance_sheet"]
    assert liquidity["tools"] == ["balance_sheet", "cash_flow"]
    assert liquidity["optional_tools"] == [
        {
            "name": "cash_flow",
            "reason": "Checks whether operations replenish liquidity",
        }
    ]
