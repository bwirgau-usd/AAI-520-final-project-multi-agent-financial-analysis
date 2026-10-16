"""End-to-end orchestration for the investment research agents."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from src.agents import EvaluatorAgent, PlannerAgent, SynthesisAgent
from src.llm import ask_llm
from src.memory import MemoryCurator, ResearchMemoryStore
from src.state import ResearchState
from src.tools.executor import execute_tools
from src.tools.registry import TOOLS, Tool
from src.workflows.news_pipeline import NewsPipeline, build_news_pipeline

ProgressCallback = Callable[[str], None]
LlmCallable = Callable[[str], str]


@dataclass
class ResearchWorkflow:
    """Coordinate one eight-stage research run and return every artifact."""

    planner: PlannerAgent
    evaluator: EvaluatorAgent
    synthesizer: SynthesisAgent
    memory_curator: MemoryCurator
    memory_store: ResearchMemoryStore
    tools: Mapping[str, Tool]
    news_pipeline: NewsPipeline | None = None

    def run(
        self,
        symbol: str,
        *,
        remember: bool = True,
        progress: ProgressCallback | None = None,
    ) -> ResearchState:
        """Run planning through memory persistence for one stock symbol."""

        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must be a non-empty string")

        emit = progress or (lambda _message: None)
        state: ResearchState = {"symbol": normalized_symbol}
        total_stages = 8 if self.news_pipeline is not None else 7

        emit(f"1/{total_stages} Planning the research run")
        plan = self.planner.plan(normalized_symbol, self.tools.keys())
        state["plan"] = plan

        emit(f"2/{total_stages} Collecting market and financial evidence")
        observations = execute_tools(
            normalized_symbol,
            plan,
            self.tools,
            progress=emit,
        )
        state["observations"] = observations

        if self.news_pipeline is not None:
            emit("3/8 Processing current company news")
            try:
                news_analysis = self.news_pipeline.analyze(
                    normalized_symbol,
                    progress=emit,
                )
            except Exception as exc:  # noqa: BLE001 - preserve core workflow
                news_analysis = {
                    "ticker": normalized_symbol,
                    "articles": [],
                    "article_count": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            state["news_analysis"] = news_analysis
            observations["news_analysis"] = news_analysis
        validation_stage = 4 if self.news_pipeline is not None else 3
        emit(f"{validation_stage}/{total_stages} Validating tool observations")
        validation = self.evaluator.validate_observations(observations)
        state["validation"] = validation

        reflection_stage = validation_stage + 1
        emit(f"{reflection_stage}/{total_stages} Reflecting on evidence quality")
        reflection = self.evaluator.reflect(
            normalized_symbol,
            plan,
            observations,
            validation,
        )
        state["reflection"] = reflection

        synthesis_stage = reflection_stage + 1
        emit(f"{synthesis_stage}/{total_stages} Synthesizing the research report")
        report = self.synthesizer.create_report(
            normalized_symbol,
            plan,
            observations,
            reflection,
            validation,
        )
        state["report"] = report

        report_validation_stage = synthesis_stage + 1
        emit(f"{report_validation_stage}/{total_stages} Validating the research report")
        state["report_validation"] = self.evaluator.validate_report(
            report,
            observations,
        )

        if remember:
            emit(f"{total_stages}/{total_stages} Saving lessons for a future run")
            summary = self.memory_curator.summarize(
                normalized_symbol,
                report,
                reflection,
            )
            state["memory_entry"] = self.memory_store.add(
                normalized_symbol,
                summary,
                reflection["weaknesses"],
            )
        else:
            emit(f"{total_stages}/{total_stages} Memory persistence skipped")

        return state


def build_research_workflow(
    *,
    project_root: Path | str | None = None,
    llm: LlmCallable = ask_llm,
    tools: Mapping[str, Tool] | None = None,
    memory_store: ResearchMemoryStore | None = None,
    news_pipeline: NewsPipeline | None = None,
    include_news: bool | None = None,
) -> ResearchWorkflow:
    """Build the production workflow while allowing offline test doubles."""

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
        memory_curator=MemoryCurator(llm),
        memory_store=store,
        tools=dict(TOOLS if tools is None else tools),
        news_pipeline=resolved_news_pipeline,
    )
