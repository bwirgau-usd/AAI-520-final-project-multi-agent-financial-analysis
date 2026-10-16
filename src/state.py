"""Shared state definitions for the multi-agent research workflow."""

from __future__ import annotations

from typing import Any, TypedDict


class ResearchPlan(TypedDict, total=False):
    """Planner output that controls which tools the workflow executes."""

    objectives: list[str]
    tools: list[str]
    questions: list[str]
    research_request: str
    route: str
    specialists: list[str]
    memory_context: list[dict[str, Any]]


class ValidationIssue(TypedDict, total=False):
    """A deterministic data or report quality concern."""

    type: str
    tool: str
    field: str
    message: str
    value: Any


class Reflection(TypedDict):
    """Model-assisted assessment augmented with deterministic findings."""

    strengths: list[str]
    weaknesses: list[str]
    missing_information: list[str]
    suspicious_values: list[str]
    follow_up_questions: list[str]
    deterministic_issues: list[ValidationIssue]


class ResearchState(TypedDict, total=False):
    """Artifacts produced during one end-to-end research run."""

    symbol: str
    research_request: str
    remember: bool
    request_route: str
    selected_specialists: list[str]
    plan: ResearchPlan
    observations: dict[str, Any]
    specialist_analyses: dict[str, Any]
    news_analysis: dict[str, Any]
    validation: list[ValidationIssue]
    reflection: Reflection
    report: str
    draft_report: str
    report_validation: list[ValidationIssue]
    report_evaluation: dict[str, Any]
    report_evaluation_history: list[dict[str, Any]]
    report_revision_history: list[dict[str, Any]]
    report_revision_count: int
    max_report_revisions: int
    graph_trace: list[str]
    memory_entry: dict[str, Any]
