"""Project-requirement traceability for reports, notebooks, and CLI output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

PROMPT_CHAIN_STAGES = ("ingest", "preprocess", "classify", "extract", "summarize")


def build_requirement_traceability(
    state: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Map each course requirement to its implementation and run evidence."""

    plan = _mapping(state.get("plan"))
    observations = _mapping(state.get("observations"))
    reflection = _mapping(state.get("reflection"))
    news = _mapping(observations.get("news_analysis") or state.get("news_analysis"))
    graph_trace = _strings(state.get("graph_trace"))
    report_evaluations = _mappings(state.get("report_evaluation_history"))
    report_revisions = _mappings(state.get("report_revision_history"))
    articles = _mappings(news.get("articles"))
    article_revisions = sum(
        len(article.get("optimization_history", []))
        for article in articles
        if isinstance(article.get("optimization_history", []), list)
    )

    planned_tools = _strings(plan.get("tools"))
    observed_tools = [
        name for name in observations if name != "news_analysis"
    ]
    pipeline_stages = _strings(news.get("pipeline_stages"))
    prompt_chain_complete = all(
        stage in pipeline_stages for stage in PROMPT_CHAIN_STAGES
    )
    routed_articles = sum(bool(article.get("specialist")) for article in articles)
    memory_context = _mappings(plan.get("memory_context"))
    memory_actions = _mappings(plan.get("applied_memory_actions"))
    memory_entry = _mapping(state.get("memory_entry"))

    return [
        _row(
            "Agent Functions",
            "Plans research steps",
            "src/agents/planner.py; src/workflows/research_workflow.py::_plan_request",
            (
                f"Plan created with {len(plan.get('objectives', []))} objective(s), "
                f"{len(plan.get('questions', []))} question(s), and route "
                f"{state.get('request_route', 'not recorded')}."
                if plan
                else "No plan was produced in this run."
            ),
            bool(plan),
        ),
        _row(
            "Agent Functions",
            "Uses tools dynamically",
            "src/agents/planner.py; src/tools/registry.py; specialist agents",
            (
                f"Planner selected {', '.join(planned_tools) or 'no registry tools'}; "
                f"observed outputs: {', '.join(observed_tools) or 'news workflow only'}."
            ),
            bool(plan) and bool(observations),
        ),
        _row(
            "Agent Functions",
            "Self-reflects on output quality",
            "src/agents/evaluator.py::reflect; validate_observations",
            (
                f"Reflection recorded {len(reflection.get('strengths', []))} strength(s), "
                f"{len(reflection.get('weaknesses', []))} weakness(es), and "
                f"{len(reflection.get('deterministic_issues', []))} deterministic issue(s)."
                if reflection
                else "No reflection was produced in this run."
            ),
            bool(reflection),
        ),
        _row(
            "Agent Functions",
            "Learns across runs",
            "src/memory/curator.py; src/memory/memory_store.py; planner memory actions",
            (
                f"Retrieved {len(memory_context)} prior memory record(s), applied "
                f"{len(memory_actions)} structured action(s), and "
                f"{'saved a new memory' if memory_entry else 'did not save memory in this run'}."
            ),
            bool(memory_entry or memory_context or memory_actions),
        ),
        _row(
            "Workflow Patterns",
            "Prompt chaining: ingest → preprocess → classify → extract → summarize",
            "src/workflows/news_pipeline.py; src/tools/news_tools.py",
            (
                "Observed stages: " + " → ".join(pipeline_stages)
                if pipeline_stages
                else "News was not exercised by this route."
            ),
            prompt_chain_complete,
        ),
        _row(
            "Workflow Patterns",
            "Routes requests and content to specialists",
            "src/agents/router.py; LangGraph conditional edges",
            (
                f"Request route: {state.get('request_route', 'not recorded')}; "
                f"selected specialists: {', '.join(_strings(state.get('selected_specialists'))) or 'none'}; "
                f"routed articles: {routed_articles}."
            ),
            bool(state.get("request_route")) and "plan_request" in graph_trace,
        ),
        _row(
            "Workflow Patterns",
            "Evaluator–optimizer refinement",
            "src/agents/evaluator.py; src/agents/optimizer.py; evaluator–optimizer graph edges",
            (
                f"Complete-report evaluations: {len(report_evaluations)}; report revisions: "
                f"{len(report_revisions)}; article revisions: {article_revisions}."
            ),
            bool(report_evaluations),
        ),
        _row(
            "Technology",
            "Uses financial datasets and APIs",
            "Yahoo Finance, NewsAPI/Google News, and SEC EDGAR adapters under src/data_sources",
            _data_source_evidence(observations, news),
            bool(observations),
        ),
        _row(
            "Technology",
            "Uses GitHub and documents collaboration",
            "GitHub repository link, commit history, README Team and Contributions section",
            "Repository-hosting and collaboration evidence is documented in README.md and Git history.",
            True,
            static=True,
        ),
        _row(
            "Technology",
            "Includes a project README",
            "README.md",
            "README documents setup, architecture, requirements, usage, testing, and contributions.",
            True,
            static=True,
        ),
        _row(
            "Technology",
            "Follows PEP 8 style",
            "Python modules under src/ and tests/; Ruff configuration/dependency",
            "Verify with: ruff check src tests. The regression suite also runs with pytest.",
            True,
            static=True,
        ),
    ]


def _row(
    category: str,
    requirement: str,
    implementation: str,
    run_evidence: str,
    demonstrated: bool,
    *,
    static: bool = False,
) -> dict[str, str]:
    if static:
        status = "documented"
    elif demonstrated:
        status = "demonstrated"
    else:
        status = "implemented—not exercised in this run"
    return {
        "category": category,
        "requirement": requirement,
        "status": status,
        "implementation": implementation,
        "run_evidence": run_evidence,
    }


def _data_source_evidence(
    observations: Mapping[str, Any],
    news: Mapping[str, Any],
) -> str:
    sources: list[str] = []
    if any(
        name in observations
        for name in (
            "price_data",
            "company_info",
            "financials",
            "cash_flow",
            "balance_sheet",
            "financial_growth",
        )
    ):
        sources.append("Yahoo Finance")
    if "sec_edgar" in observations:
        sources.append("SEC EDGAR")
    if news:
        source_counts = _mapping(news.get("source_counts"))
        sources.extend(str(name) for name in source_counts)
    return (
        "Run evidence includes: " + ", ".join(dict.fromkeys(sources))
        if sources
        else "No external data source was exercised in this route."
    )


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mappings(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _strings(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item) for item in value if str(item)]
