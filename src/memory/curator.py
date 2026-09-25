"""Create concise, explicitly bounded notes for future research runs."""

from __future__ import annotations

import json
from collections.abc import Callable

from src.state import Reflection


class MemoryCurator:
    """Summarize reusable lessons without treating them as live evidence."""

    def __init__(self, llm: Callable[[str], str]) -> None:
        self._llm = llm

    def summarize(self, symbol: str, report: str, reflection: Reflection) -> str:
        """Return a short note suitable for the persistent memory store."""

        prompt = f"""
Summarize reusable research lessons from this {symbol} run in at most 120 words.
Focus on evidence coverage, data-quality problems, and improvements for a future
run. Do not present time-sensitive values as permanent facts.

Reflection:
{json.dumps(reflection, default=str)}

Report:
{report}
""".strip()
        summary = self._llm(prompt).strip()
        if not summary:
            raise RuntimeError("The memory model returned an empty summary.")
        return summary
