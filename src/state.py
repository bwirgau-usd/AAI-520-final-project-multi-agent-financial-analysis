"""Shared state definitions for the multi-agent research workflow."""

from __future__ import annotations

from typing import Any, TypedDict


class ResearchPlan(TypedDict):
    """Planner output that controls which tools the workflow executes."""

    objectives: list[str]
    tools: list[str]
    questions: list[str]


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
    plan: ResearchPlan
    observations: dict[str, Any]
    validation: list[ValidationIssue]
    reflection: Reflection
    report: str
    report_validation: list[ValidationIssue]
    memory_entry: dict[str, Any]
