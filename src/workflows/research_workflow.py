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


ProgressCallback = Callable[[str], None]
LlmCallable = Callable[[str], str]


@dataclass
class ResearchWorkflow:
    """Coordinate one seven-stage research run and return every artifact."""

    planner: PlannerAgent
    evaluator: EvaluatorAgent
    synthesizer: SynthesisAgent
    memory_curator: MemoryCurator
    memory_store: ResearchMemoryStore
    tools: Mapping[str, Tool]

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

        emit("1/7 Planning the research run")
        plan = self.planner.plan(normalized_symbol, self.tools.keys())
        state["plan"] = plan

        emit("2/7 Collecting market and financial evidence")
        observations = execute_tools(
            normalized_symbol,
            plan,
            self.tools,
            progress=emit,
        )
        state["observations"] = observations

        emit("3/7 Validating tool observations")
        validation = self.evaluator.validate_observations(observations)
        state["validation"] = validation

        emit("4/7 Reflecting on evidence quality")
        reflection = self.evaluator.reflect(
            normalized_symbol,
            plan,
            observations,
            validation,
        )
        state["reflection"] = reflection

        emit("5/7 Synthesizing the research report")
        report = self.synthesizer.create_report(
            normalized_symbol,
            plan,
            observations,
            reflection,
            validation,
        )
        state["report"] = report

        emit("6/7 Validating the research report")
        state["report_validation"] = self.evaluator.validate_report(
            report,
            observations,
        )

        if remember:
            emit("7/7 Saving lessons for a future run")
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
            emit("7/7 Memory persistence skipped")

        return state


def build_research_workflow(
    *,
    project_root: Path | str | None = None,
    llm: LlmCallable = ask_llm,
    tools: Mapping[str, Tool] | None = None,
    memory_store: ResearchMemoryStore | None = None,
) -> ResearchWorkflow:
    """Build the production workflow while allowing offline test doubles."""

    store = memory_store or ResearchMemoryStore.from_env(project_root)
    return ResearchWorkflow(
        planner=PlannerAgent(llm, store),
        evaluator=EvaluatorAgent(llm),
        synthesizer=SynthesisAgent(llm),
        memory_curator=MemoryCurator(llm),
        memory_store=store,
        tools=dict(TOOLS if tools is None else tools),
    )
