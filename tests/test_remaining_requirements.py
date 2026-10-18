"""Behavioral coverage for request routing, report scoring, and learning."""

import json

from src.agents.evaluator import EvaluatorAgent
from src.agents.router import ResearchRequestRouter
from src.memory import ResearchMemoryStore
from src.workflows import build_news_pipeline, build_research_workflow


def _strong_market_report() -> str:
    return """# Market Research Answer

## Request and evidence
The requested price and volatility analysis uses Yahoo Finance source evidence.
The latest observed price is $110.00, compared with 100 initially, for a 10.00%
one-year return.
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
    tool_calls = []

    def price_data(symbol):
        tool_calls.append(symbol)
        return {
            "latest_price": 110,
            "1y_return_percent": 10,
        }

    workflow = build_research_workflow(
        llm=LearningLlm(),
        tools={"price_data": price_data},
        memory_store=store,
        max_report_revisions=0,
    )
    request = "Analyze market price, return, and volatility"

    first = workflow.run("AAPL", request)
    second = workflow.run(
        "AAPL",
        request,
        remember=False,
        evidence_snapshot=first,
    )

    assert first["plan"]["objectives"] == ["Establish a price baseline"]
    assert second["plan"]["objectives"][0] == "Apply saved volatility feedback"
    assert any(
        "volatility and drawdown context" in objective
        for objective in second["plan"]["objectives"]
    )
    assert second["plan"]["applied_memory_actions"]
    assert second["plan"]["memory_context"]
    assert second["request_route"] == "market"
    assert second["evidence_reused"] is True
    assert tool_calls == ["AAPL"]


class ActionableLearningLlm:
    def __call__(self, prompt):
        if "planning an evidence-based" in prompt:
            return json.dumps(
                {
                    "objectives": ["Assess the supplied company event"],
                    "tools": [],
                    "questions": ["What event does the article establish?"],
                }
            )
        if "Classify this financial article" in prompt:
            return json.dumps({"category": "news", "confidence": 0.95})
        if "Extract only facts" in prompt:
            return json.dumps(
                {
                    "company": "Example",
                    "event": "acquisition",
                    "event_dates": [],
                    "sentiment": "neutral",
                    "financial_numbers": [],
                    "events": ["acquisition"],
                    "keywords": ["acquisition"],
                }
            )
        if "Summarize the supplied financial article" in prompt:
            return json.dumps(
                {"summary": "Example announced an acquisition update."}
            )
        if "financial news analyst" in prompt or "optimizing a financial-news" in prompt:
            return json.dumps(
                {
                    "specialist": "news",
                    "observations": [
                        "Headline: Example announces an acquisition update",
                        "Detected events: acquisition",
                    ],
                    "interpretation": (
                        "The supplied article provides evidence relevant to the "
                        "reported company development; its investment significance "
                        "requires corroboration."
                    ),
                    "uncertainties": ["Only a provider snippet was supplied."],
                }
            )
        if "research quality reviewer" in prompt:
            return json.dumps(
                {
                    "strengths": ["The event is traceable to a source URL"],
                    "weaknesses": ["News analysis lacks financial implications"],
                    "missing_information": [],
                    "suspicious_values": [],
                    "follow_up_questions": [],
                }
            )
        if "Write a concise" in prompt:
            if "Apply prior-run feedback" in prompt:
                return (
                    "# News report\n\nThe evidence does not establish whether the "
                    "event affects revenue, costs, cash flow, or valuation, so "
                    "the financial implication remains uncertain."
                )
            return "# News report\n\nThe article describes an acquisition event."
        if "Summarize reusable" in prompt:
            return "Explain the financial implications of material news events."
        raise AssertionError(f"Unexpected prompt: {prompt}")


class OneArticleYahoo:
    def __init__(self):
        self.calls = 0

    def get_news(self, _symbol, max_articles=8):
        self.calls += 1
        return [
            {
                "title": "Example announces an acquisition update",
                "summary": "Example announced an acquisition update.",
                "description": "The company provided no financial forecast.",
                "content": "",
                "publisher": "Example Wire",
                "source": "Yahoo Finance",
                "url": "https://example.com/acquisition",
                "published_at": "2026-10-01T12:00:00Z",
                "author": None,
            }
        ][:max_articles]


class NoNewsApi:
    def get_articles(self, _symbol, max_articles=8):
        return []


def test_saved_lesson_changes_and_improves_replay_of_same_evidence(tmp_path):
    llm = ActionableLearningLlm()
    yahoo = OneArticleYahoo()
    news_pipeline = build_news_pipeline(
        llm,
        yahoo_client=yahoo,
        news_api_client=NoNewsApi(),
        max_optimizer_iterations=1,
        substantive_reasoning_threshold=60,
    )
    workflow = build_research_workflow(
        llm=llm,
        tools={},
        news_pipeline=news_pipeline,
        memory_store=ResearchMemoryStore(tmp_path / "memory.json"),
        max_report_revisions=0,
    )
    request = "Summarize recent company news and events"

    first = workflow.run("AAPL", request)
    second = workflow.run(
        "AAPL",
        request,
        remember=False,
        evidence_snapshot=first,
    )

    lesson = first["memory_entry"]["lessons"][0]
    action = lesson["next_run_action"]
    first_article = first["news_analysis"]["articles"][0]
    second_article = second["news_analysis"]["articles"][0]
    assert lesson["weakness"] == "News analysis lacks financial implications"
    assert lesson in second["plan"]["applied_memory_actions"]
    assert action in second["news_analysis"]["planning_actions"]
    assert second["evidence_reused"] is True
    assert second["news_analysis"]["evidence_reused"] is True
    assert yahoo.calls == 1
    assert (
        first["news_analysis"]["source_articles"]
        == second["news_analysis"]["source_articles"]
    )
    assert first_article["evaluation_history"][0]["substantive_reasoning_score"] == 50
    assert second_article["evaluation_history"][0]["substantive_reasoning_score"] == 100
    assert "revenue, costs, cash flow, or valuation" in second_article[
        "optimized_analysis"
    ]["interpretation"]
    assert "financial implication remains uncertain" in second["report"]


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


class RegressingRevisionLlm(RevisionLlm):
    def __init__(self):
        self.revision_count = 0

    def __call__(self, prompt):
        if "Revise this complete" in prompt:
            self.revision_count += 1
            if self.revision_count == 1:
                return (
                    _strong_market_report()
                    .replace(
                        "Yahoo Finance source evidence",
                        "provider evidence",
                    )
                    .replace(
                        "https://finance.yahoo.com",
                        "the provider dataset",
                    )
                    .replace("Source coverage", "Coverage")
                )
            return "# Worse revision\n\nPrice is discussed without adequate support."
        return super().__call__(prompt)


def test_graph_keeps_the_best_report_when_a_later_revision_regresses(tmp_path):
    workflow = build_research_workflow(
        llm=RegressingRevisionLlm(),
        tools={
            "price_data": lambda _symbol: {
                "latest_price": 110,
                "1y_return_percent": 10,
            }
        },
        memory_store=ResearchMemoryStore(tmp_path / "memory.json"),
        max_report_revisions=2,
    )

    result = workflow.run(
        "AAPL",
        "Analyze market price, return, and volatility",
        remember=False,
    )

    scores = [item["score"] for item in result["report_evaluation_history"]]
    assert len(scores) == 3
    assert result["report_evaluation"]["score"] == max(scores)
    assert "Worse revision" not in result["report"]
