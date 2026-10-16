"""Offline tests for persistent research memory."""

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from src.memory import ResearchMemoryStore


class TestResearchMemoryStore(unittest.TestCase):
    def test_missing_and_malformed_files_are_empty(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "memory.json"
            store = ResearchMemoryStore(path)
            self.assertEqual(store.load(), [])

            path.write_text("not-json", encoding="utf-8")
            self.assertEqual(store.load(), [])

    def test_add_creates_directory_and_persists_utc_entry(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "nested" / "memory.json"
            store = ResearchMemoryStore(path)

            entry = store.add(" aapl ", "Research summary", ["Missing filing"])

            self.assertEqual(entry["symbol"], "AAPL")
            self.assertIsNotNone(datetime.fromisoformat(entry["date"]).tzinfo)
            self.assertEqual(ResearchMemoryStore(path).load(), [entry])
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_filters_symbols_without_case_sensitivity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = ResearchMemoryStore(Path(temporary_directory) / "memory.json")
            store.add("AAPL", "Apple")
            store.add("MSFT", "Microsoft")

            entries = store.for_symbol("aapl")

            self.assertEqual([entry["summary"] for entry in entries], ["Apple"])

    def test_limits_entries(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = ResearchMemoryStore(
                Path(temporary_directory) / "memory.json", max_entries=2
            )
            store.add("AAPL", "First")
            store.add("AAPL", "Second")
            store.add("AAPL", "Third")

            self.assertEqual(
                [entry["summary"] for entry in store.load()],
                ["Second", "Third"],
            )

    def test_loads_versioned_entry_format(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "memory.json"
            entry = {"symbol": "AAPL", "summary": "Existing"}
            path.write_text(
                json.dumps({"version": 1, "entries": [entry]}),
                encoding="utf-8",
            )

            self.assertEqual(ResearchMemoryStore(path).load(), [entry])

    def test_from_env_resolves_relative_path_from_project_root(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch.dict(
                os.environ,
                {"MEMORY_PATH": "state/research.json"},
            ):
                store = ResearchMemoryStore.from_env(root)

            self.assertEqual(
                store.path,
                (root / "state/research.json").resolve(),
            )

    def test_rejects_empty_symbol_and_invalid_limit(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = ResearchMemoryStore(Path(temporary_directory) / "memory.json")
            with self.assertRaisesRegex(ValueError, "non-empty"):
                store.for_symbol(" ")

        with self.assertRaisesRegex(ValueError, "at least 1"):
            ResearchMemoryStore("memory.json", max_entries=0)
