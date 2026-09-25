"""Optional command-line entry point for the research workflow."""

from __future__ import annotations

from src.reporting import render_console_summary
from src.workflows import build_research_workflow

def main() -> None:
    """Prompt for a ticker, run the workflow, and print its report."""

    symbol = input("Stock symbol: ").strip()
    workflow = build_research_workflow()
    result = workflow.run(symbol, progress=print)
    print()
    print(render_console_summary(result))
    print()
    print(result["report"])


if __name__ == "__main__":  # pragma: no cover - interactive entry point
    main()
