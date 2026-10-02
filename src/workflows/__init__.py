"""Public workflow interfaces."""

__all__ = ["ResearchWorkflow", "build_research_workflow"]


def __getattr__(name: str):
    # Lazy, PEP 562 style: research_workflow transitively imports
    # src.tools.registry -> src.agents.news_agent -> src.workflows.news_pipeline,
    # and importing that submodule always imports this package first. An
    # eager import here would make that a circular import.
    if name in __all__:
        from . import research_workflow

        return getattr(research_workflow, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
