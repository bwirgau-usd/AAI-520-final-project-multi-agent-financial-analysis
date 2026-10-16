"""LangGraph orchestration for the end-to-end investment research workflow."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.agents import (
    EvaluatorAgent,
    FinancialResearchAgent,
    MarketResearchAgent,
    OptimizerAgent,
    PlannerAgent,
    ResearchRequestRouter,
    SynthesisAgent,
)
from src.llm import ask_llm
from src.memory import MemoryCurator, ResearchMemoryStore
from src.state import ResearchState
from src.tools.registry import TOOLS, Tool
from src.workflows.news_pipeline import NewsPipeline, build_news_pipeline

ProgressCallback = Callable[[str], None]
LlmCallable = Callable[[str], str]
DEFAULT_RESEARCH_REQUEST = (
    "Provide a comprehensive investment research report covering market "
    "performance, financial condition, SEC evidence, and recent news."
)


@dataclass
class ResearchWorkflow:
    """Coordinate request routing and evaluator-optimizer report cycles."""

    planner: PlannerAgent
    evaluator: EvaluatorAgent
    synthesizer: SynthesisAgent
    optimizer: OptimizerAgent
    memory_curator: MemoryCurator
    memory_store: ResearchMemoryStore
    tools: Mapping[str, Tool]
    news_pipeline: NewsPipeline | None = None
    request_router: ResearchRequestRouter = field(default_factory=ResearchRequestRouter)
    market_agent: MarketResearchAgent = field(default_factory=MarketResearchAgent)
    financial_agent: FinancialResearchAgent = field(default_factory=FinancialResearchAgent)
    report_score_threshold: float = 75
    default_max_report_revisions: int = 2
    graph: Any = field(init=False, repr=False)
    _emit: ProgressCallback = field(init=False, repr=False, default=lambda _message: None)

    def __post_init__(self) -> None:
        self.graph = self._build_graph()

    def run(
        self,
        symbol: str,
        research_request: str | None = None,
        *,
        remember: bool = True,
        progress: ProgressCallback | None = None,
        max_report_revisions: int | None = None,
    ) -> ResearchState:
        """Run a request-aware research graph for one stock symbol."""

        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must be a non-empty string")
        request = (research_request or DEFAULT_RESEARCH_REQUEST).strip()
        if not request:
            raise ValueError("research_request must be a non-empty string")

        self._emit = progress or (lambda _message: None)
        initial: ResearchState = {
            "symbol": normalized_symbol,
            "research_request": request,
            "remember": remember,
            "max_report_revisions": (
                self.default_max_report_revisions
                if max_report_revisions is None
                else max(0, int(max_report_revisions))
            ),
            "report_revision_count": 0,
            "report_evaluation_history": [],
            "report_revision_history": [],
            "graph_trace": [],
        }
        result = self.graph.invoke(initial, config={"recursion_limit": 50})
        return ResearchState(result)

    def _build_graph(self) -> Any:
        builder = StateGraph(ResearchState)
        builder.add_node("plan_request", self._plan_request)
        builder.add_node("market_research", self._market_research)
        builder.add_node("financial_research", self._financial_research)
        builder.add_node("news_research", self._news_research)
        builder.add_node("comprehensive_research", self._comprehensive_research)
        builder.add_node("validate_observations", self._validate_observations)
        builder.add_node("reflect", self._reflect)
        builder.add_node("synthesize", self._synthesize)
        builder.add_node("evaluate_report", self._evaluate_report)
        builder.add_node("revise_report", self._revise_report)
        builder.add_node("finalize", self._finalize)
        builder.add_node("remember", self._remember)

        builder.add_edge(START, "plan_request")
        builder.add_conditional_edges(
            "plan_request",
            self._research_route,
            {
                "market": "market_research",
                "financial": "financial_research",
                "news": "news_research",
                "comprehensive": "comprehensive_research",
            },
        )
        for node in (
            "market_research",
            "financial_research",
            "news_research",
            "comprehensive_research",
        ):
            builder.add_edge(node, "validate_observations")
        builder.add_edge("validate_observations", "reflect")
        builder.add_edge("reflect", "synthesize")
        builder.add_edge("synthesize", "evaluate_report")
        builder.add_conditional_edges(
            "evaluate_report",
            self._evaluation_route,
            {"revise": "revise_report", "finish": "finalize"},
        )
        builder.add_edge("revise_report", "evaluate_report")
        builder.add_conditional_edges(
            "finalize",
            self._memory_route,
            {"remember": "remember", "finish": END},
        )
        builder.add_edge("remember", END)
        return builder.compile()

    def _plan_request(self, state: ResearchState) -> ResearchState:
        self._emit("Planning and routing the research request")
        routing = self.request_router.route(
            state["research_request"],
            self.tools.keys(),
            has_news_pipeline=self.news_pipeline is not None,
        )
        plan = self.planner.plan(
            state["symbol"],
            routing["tools"],
            state["research_request"],
            route=routing["route"],
            specialists=routing["specialists"],
        )
        return {
            "request_route": routing["route"],
            "selected_specialists": routing["specialists"],
            "plan": plan,
            "graph_trace": self._trace(state, "plan_request"),
        }

    @staticmethod
    def _research_route(state: ResearchState) -> str:
        return state.get("request_route", "comprehensive")

    def _market_research(self, state: ResearchState) -> ResearchState:
        self._emit("Running the market specialist")
        result = self.market_agent.research(
            state["symbol"],
            state["plan"],
            self.tools,
            progress=self._emit,
        )
        return {
            "observations": result["observations"],
            "specialist_analyses": {"market": result["analysis"]},
            "graph_trace": self._trace(state, "market_research"),
        }

    def _financial_research(self, state: ResearchState) -> ResearchState:
        self._emit("Running the financial specialist")
        result = self.financial_agent.research(
            state["symbol"],
            state["plan"],
            self.tools,
            progress=self._emit,
        )
        return {
            "observations": result["observations"],
            "specialist_analyses": {"financial": result["analysis"]},
            "graph_trace": self._trace(state, "financial_research"),
        }

    def _news_research(self, state: ResearchState) -> ResearchState:
        self._emit("Running the news specialist and prompt chain")
        news_analysis = self._run_news(state)
        return {
            "observations": {"news_analysis": news_analysis},
            "news_analysis": news_analysis,
            "specialist_analyses": {
                "news": {
                    "article_count": news_analysis.get("article_count", 0),
                    "average_score": news_analysis.get("average_score"),
                    "routing_counts": news_analysis.get("routing_counts", {}),
                }
            },
            "graph_trace": self._trace(state, "news_research"),
        }

    def _comprehensive_research(self, state: ResearchState) -> ResearchState:
        self._emit("Running all selected research specialists")
        market = self.market_agent.research(
            state["symbol"], state["plan"], self.tools, progress=self._emit
        )
        financial = self.financial_agent.research(
            state["symbol"], state["plan"], self.tools, progress=self._emit
        )
        observations = {**market["observations"], **financial["observations"]}
        analyses = {
            "market": market["analysis"],
            "financial": financial["analysis"],
        }
        updates: ResearchState = {}
        if self.news_pipeline is not None:
            news_analysis = self._run_news(state)
            observations["news_analysis"] = news_analysis
            analyses["news"] = {
                "article_count": news_analysis.get("article_count", 0),
                "average_score": news_analysis.get("average_score"),
                "routing_counts": news_analysis.get("routing_counts", {}),
            }
            updates["news_analysis"] = news_analysis
        updates.update(
            {
                "observations": observations,
                "specialist_analyses": analyses,
                "graph_trace": self._trace(state, "comprehensive_research"),
            }
        )
        return updates

    def _run_news(self, state: ResearchState) -> dict[str, Any]:
        if self.news_pipeline is None:
            return {
                "ticker": state["symbol"],
                "articles": [],
                "article_count": 0,
                "error": "The news pipeline is not configured.",
            }
        try:
            return self.news_pipeline.analyze(
                state["symbol"],
                state["research_request"],
                progress=self._emit,
            )
        except Exception as exc:  # noqa: BLE001 - preserve other specialists
            return {
                "ticker": state["symbol"],
                "articles": [],
                "article_count": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _validate_observations(self, state: ResearchState) -> ResearchState:
        self._emit("Validating specialist observations")
        return {
            "validation": self.evaluator.validate_observations(state["observations"]),
            "graph_trace": self._trace(state, "validate_observations"),
        }

    def _reflect(self, state: ResearchState) -> ResearchState:
        self._emit("Reflecting on evidence quality")
        return {
            "reflection": self.evaluator.reflect(
                state["symbol"],
                state["plan"],
                state["observations"],
                state["validation"],
            ),
            "graph_trace": self._trace(state, "reflect"),
        }

    def _synthesize(self, state: ResearchState) -> ResearchState:
        self._emit("Synthesizing the draft report")
        report = self.synthesizer.create_report(
            state["symbol"],
            state["plan"],
            state["observations"],
            state["reflection"],
            state["validation"],
            state["research_request"],
            state.get("specialist_analyses", {}),
        )
        return {
            "draft_report": report,
            "report": report,
            "graph_trace": self._trace(state, "synthesize"),
        }

    def _evaluate_report(self, state: ResearchState) -> ResearchState:
        self._emit("Scoring the complete report")
        evaluation = self.evaluator.evaluate_report(
            state["report"],
            state["observations"],
            state["research_request"],
            state["request_route"],
            threshold=self.report_score_threshold,
        )
        evaluation_history = [*state.get("report_evaluation_history", []), evaluation]
        revision_history = [*state.get("report_revision_history", [])]
        if revision_history and revision_history[-1].get("after_score") is None:
            revision_history[-1] = {
                **revision_history[-1],
                "after_score": evaluation["score"],
            }
        return {
            "report_evaluation": evaluation,
            "report_evaluation_history": evaluation_history,
            "report_revision_history": revision_history,
            "graph_trace": self._trace(state, "evaluate_report"),
        }

    @staticmethod
    def _evaluation_route(state: ResearchState) -> str:
        evaluation = state.get("report_evaluation", {})
        if evaluation.get("passed"):
            return "finish"
        if state.get("report_revision_count", 0) >= state.get(
            "max_report_revisions", 0
        ):
            return "finish"
        return "revise"

    def _revise_report(self, state: ResearchState) -> ResearchState:
        iteration = state.get("report_revision_count", 0) + 1
        self._emit(f"Revising the complete report (iteration {iteration})")
        report = self.optimizer.optimize_report(
            state["symbol"],
            state["research_request"],
            state["report"],
            state["report_evaluation"],
            state["observations"],
            state.get("specialist_analyses", {}),
        )
        history = [
            *state.get("report_revision_history", []),
            {
                "iteration": iteration,
                "before_score": state["report_evaluation"]["score"],
                "after_score": None,
                "feedback": state["report_evaluation"].get("feedback", []),
            },
        ]
        return {
            "report": report,
            "report_revision_count": iteration,
            "report_revision_history": history,
            "graph_trace": self._trace(state, "revise_report"),
        }

    def _finalize(self, state: ResearchState) -> ResearchState:
        self._emit("Finalizing the evaluated report")
        return {
            "report_validation": state.get("report_evaluation", {}).get(
                "validation_issues", []
            ),
            "graph_trace": self._trace(state, "finalize"),
        }

    @staticmethod
    def _memory_route(state: ResearchState) -> str:
        return "remember" if state.get("remember", True) else "finish"

    def _remember(self, state: ResearchState) -> ResearchState:
        self._emit("Saving evaluator feedback for a future run")
        summary = self.memory_curator.summarize(
            state["symbol"],
            state["report"],
            state["reflection"],
            state.get("report_evaluation"),
            state["research_request"],
        )
        return {
            "memory_entry": self.memory_store.add(
                state["symbol"],
                summary,
                state["reflection"]["weaknesses"],
            ),
            "graph_trace": self._trace(state, "remember"),
        }

    @staticmethod
    def _trace(state: ResearchState, node: str) -> list[str]:
        return [*state.get("graph_trace", []), node]


def build_research_workflow(
    *,
    project_root: Path | str | None = None,
    llm: LlmCallable = ask_llm,
    tools: Mapping[str, Tool] | None = None,
    memory_store: ResearchMemoryStore | None = None,
    news_pipeline: NewsPipeline | None = None,
    include_news: bool | None = None,
    report_score_threshold: float | None = None,
    max_report_revisions: int | None = None,
) -> ResearchWorkflow:
    """Build the production graph while allowing fully offline test doubles."""

    store = memory_store or ResearchMemoryStore.from_env(project_root)
    should_build_news = (
        tools is None if include_news is None else include_news
    ) and news_pipeline is None
    resolved_news_pipeline = (
        build_news_pipeline(llm) if should_build_news else news_pipeline
    )
    return ResearchWorkflow(
        planner=PlannerAgent(llm, store),
        evaluator=EvaluatorAgent(llm),
        synthesizer=SynthesisAgent(llm),
        optimizer=OptimizerAgent(llm),
        memory_curator=MemoryCurator(llm),
        memory_store=store,
        tools=dict(TOOLS if tools is None else tools),
        news_pipeline=resolved_news_pipeline,
        report_score_threshold=(
            report_score_threshold
            if report_score_threshold is not None
            else _float_env("REPORT_SCORE_THRESHOLD", 75)
        ),
        default_max_report_revisions=(
            max_report_revisions
            if max_report_revisions is not None
            else _int_env("MAX_REPORT_REVISIONS", 2)
        ),
    )


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return max(0.0, min(float(os.getenv(name, str(default))), 100.0))
    except ValueError:
        return default
