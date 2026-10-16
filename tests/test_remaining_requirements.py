"""Behavioral coverage for request routing, report scoring, and learning."""

import json

from src.agents.evaluator import EvaluatorAgent
from src.agents.router import ResearchRequestRouter
from src.memory import ResearchMemoryStore
from src.workflows import build_research_workflow


def _strong_market_report() -> str:
    return """# Market Research Answer

## Request and evidence
The requested price and volatility analysis uses Yahoo Finance source evidence.
The latest observed price is 110, compared with 100 initially, for a 10% return.
One-month return is 2%, three-month return is 6%, and annualized volatility is
22%. Volume is 1,200 versus average volume of 1,000. The 52-week range is 80 to
120, according to the supplied observations at https://finance.yahoo.com.

## Interpretation
The positive return suggests momentum because the latest price exceeds the
starting price. However, a 15% drawdown indicates meaningful risk while the
volume comparison provides trading context. This interpretation is separate
from the observed facts and does not predict future performance.

## Risks and uncertainty
Market history can change and uncertainty remains. The evidence is historical,
so it does not guarantee a future result. Source coverage and calculation
periods should be verified before relying on this report.
"""


def test_routes_user_requests_to_the_expected_specialists():
    router = ResearchRequestRouter()
    tools = {
        "price_data",
        "company_info",
        "financials",
        "cash_flow",
        "balance_sheet",
        "financial_growth",
        "sec_edgar",
    }

    assert router.route(
        "Analyze price, volatility, and volume", tools, has_news_pipeline=True
    )["route"] == "market"
    assert router.route(
        "Review revenue, debt, and the balance sheet", tools, has_news_pipeline=True
    )["route"] == "financial"
    assert router.route(
        "Summarize recent news sentiment and catalysts", tools, has_news_pipeline=True
    )["route"] == "news"
    assert router.route(
        "Compare market returns with earnings and recent news",
        tools,
        has_news_pipeline=True,
    )["route"] == "comprehensive"


def test_scores_weak_and_strong_complete_reports():
    evaluator = EvaluatorAgent(lambda _prompt: "{}")
    observations = {"price_data": {"latest_price": 110, "1y_return_percent": 10}}

    weak = evaluator.evaluate_report(
        "# Note\n\nLooks fine.", observations, "Analyze the market", "market"
    )
    strong = evaluator.evaluate_report(
        _strong_market_report(), observations, "Analyze the market", "market"
    )

    assert weak["passed"] is False
    assert weak["score"] < strong["score"]
    assert strong["passed"] is True
    assert set(strong["criteria"]) == {
        "completeness",
        "grounding",
        "reasoning",
        "consistency",
        "sources",
        "clarity",
    }


class LearningLlm:
    def __call__(self, prompt):
        if "planning an evidence-based" in prompt:
            learned = "Add volatility context next time" in prompt
            return json.dumps(
                {
                    "objectives": [
                        "Apply saved volatility feedback"
                        if learned
                        else "Establish a price baseline"
                    ],
                    "tools": ["price_data"],
                    "questions": ["How did the price behave?"],
                }
            )
        if "research quality reviewer" in prompt:
            return json.dumps(
                {
                    "strengths": ["Price history is available"],
                    "weaknesses": ["Volatility context is limited"],
                    "missing_information": [],
                    "suspicious_values": [],
                    "follow_up_questions": [],
                }
            )
        if "Write a concise" in prompt:
            return "# Market report\n\nPrice return and volatility are reviewed."
        if "Summarize reusable" in prompt:
            return "Add volatility context next time."
        raise AssertionError(f"Unexpected prompt: {prompt}")


def test_memory_changes_the_second_run_plan(tmp_path):
    store = ResearchMemoryStore(tmp_path / "memory.json")
    workflow = build_research_workflow(
        llm=LearningLlm(),
        tools={
            "price_data": lambda _symbol: {
                "latest_price": 110,
                "1y_return_percent": 10,
            }
        },
        memory_store=store,
        max_report_revisions=0,
    )
    request = "Analyze market price, return, and volatility"

    first = workflow.run("AAPL", request)
    second = workflow.run("AAPL", request, remember=False)

    assert first["plan"]["objectives"] == ["Establish a price baseline"]
    assert second["plan"]["objectives"] == ["Apply saved volatility feedback"]
    assert second["plan"]["memory_context"]
    assert second["request_route"] == "market"


class RevisionLlm:
    def __call__(self, prompt):
        if "planning an evidence-based" in prompt:
            return json.dumps(
                {
                    "objectives": ["Analyze the market"],
                    "tools": ["price_data"],
                    "questions": ["What does price performance show?"],
                }
            )
        if "research quality reviewer" in prompt:
            return json.dumps(
                {
                    "strengths": ["Price evidence"],
                    "weaknesses": [],
                    "missing_information": [],
                    "suspicious_values": [],
                    "follow_up_questions": [],
                }
            )
        if "Write a concise" in prompt:
            return "# Draft\n\nPrice increased."
        if "Revise this complete" in prompt:
            return _strong_market_report()
        raise AssertionError(f"Unexpected prompt: {prompt}")


def test_graph_revises_and_re_evaluates_the_complete_report(tmp_path):
    workflow = build_research_workflow(
        llm=RevisionLlm(),
        tools={
            "price_data": lambda _symbol: {
                "latest_price": 110,
                "1y_return_percent": 10,
            }
        },
        memory_store=ResearchMemoryStore(tmp_path / "memory.json"),
        max_report_revisions=1,
    )

    result = workflow.run(
        "AAPL",
        "Analyze market price, return, and volatility",
        remember=False,
    )

    assert result["draft_report"] != result["report"]
    assert len(result["report_evaluation_history"]) == 2
    assert result["report_revision_history"][0]["after_score"] > result[
        "report_revision_history"
    ][0]["before_score"]
    assert result["graph_trace"].count("evaluate_report") == 2
