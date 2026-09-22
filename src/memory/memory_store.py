"""Persistent memory operations for lessons learned across research runs.

Memory is stored as JSON, keyed by ticker symbol, so the Planner can look up
prior weaknesses before building a new research plan. Each entry keeps a
timestamp so stale notes can be told apart from current findings.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_MEMORY_PATH = "data/memory/research_memory.json"


def _memory_path() -> Path:
    return Path(os.getenv("MEMORY_PATH", _DEFAULT_MEMORY_PATH))


def _read_store() -> dict[str, Any]:
    path = _memory_path()
    if not path.exists():
        return {"version": 1, "entries": {}}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    data.setdefault("entries", {})
    return data


def _write_store(data: dict[str, Any]) -> None:
    path = _memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_memory(symbol: str) -> list[dict[str, Any]]:
    """Return prior research notes for a symbol, most recent first."""
    entries = _read_store()["entries"].get(symbol.upper(), [])
    return sorted(entries, key=lambda e: e.get("timestamp", ""), reverse=True)


def save_memory(
    symbol: str,
    feedback: str,
    research_topics: list[str] | None = None,
) -> dict[str, Any]:
    """Append a new memory entry for a symbol and persist it to disk."""
    data = _read_store()
    symbol_key = symbol.upper()

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "feedback": feedback,
        "research_topics": research_topics or [],
    }

    data["entries"].setdefault(symbol_key, []).append(entry)
    _write_store(data)

    return entry
