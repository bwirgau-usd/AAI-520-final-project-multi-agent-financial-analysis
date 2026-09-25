"""Persistent memory operations for lessons learned across research runs."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEMORY_PATH = Path("data/memory/research_memory.json")


class ResearchMemoryStore:
    """Store a bounded collection of timestamped research notes in JSON."""

    def __init__(self, path: Path | str, max_entries: int = 20) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self.path = Path(path)
        self.max_entries = max_entries

    @classmethod
    def from_env(
        cls,
        project_root: Path | str | None = None,
        *,
        max_entries: int = 20,
    ) -> "ResearchMemoryStore":
        """Build a store from ``MEMORY_PATH``, loading the project ``.env``."""

        root = Path(project_root or PROJECT_ROOT).resolve()
        try:
            from dotenv import load_dotenv
        except ImportError:  # pragma: no cover - dependency failure
            pass
        else:
            load_dotenv(root / ".env")

        path = Path(os.getenv("MEMORY_PATH", str(DEFAULT_MEMORY_PATH)))
        if not path.is_absolute():
            path = root / path
        return cls(path, max_entries=max_entries)

    def load(self) -> list[dict[str, Any]]:
        """Load valid memory entries, returning an empty list when absent."""

        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []

        if isinstance(payload, dict):
            payload = payload.get("entries", [])
        if not isinstance(payload, list):
            return []
        return [entry for entry in payload if isinstance(entry, dict)]

    def add(
        self,
        symbol: str,
        summary: str,
        weaknesses: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Append one entry and atomically persist the bounded collection."""

        normalized_symbol = self._normalize_symbol(symbol)
        entry = {
            "date": datetime.now(timezone.utc).isoformat(),
            "symbol": normalized_symbol,
            "summary": summary,
            "weaknesses": list(weaknesses or []),
        }
        entries = (self.load() + [entry])[-self.max_entries :]
        self._write(entries)
        return entry

    def for_symbol(self, symbol: str) -> list[dict[str, Any]]:
        """Return memories matching ``symbol`` without case sensitivity."""

        normalized_symbol = self._normalize_symbol(symbol)
        return [
            entry
            for entry in self.load()
            if str(entry.get("symbol", "")).strip().upper() == normalized_symbol
        ]

    def _write(self, entries: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        try:
            temporary_path.write_text(
                json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(self.path)
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must be a non-empty string")
        return normalized_symbol
