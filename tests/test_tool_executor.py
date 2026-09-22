"""Tests for safe planner-selected tool execution."""

import unittest

from src.tools.executor import execute_tools


class TestToolExecutor(unittest.TestCase):
    def test_collects_results_and_isolates_failures(self):
        plan = {
            "objectives": [],
            "tools": ["working", "failing", "missing"],
            "questions": [],
        }

        def fail(_symbol):
            raise RuntimeError("provider unavailable")

        result = execute_tools(
            "AAPL",
            plan,
            {"working": lambda symbol: {"symbol": symbol}, "failing": fail},
        )

        self.assertEqual(result["working"], {"symbol": "AAPL"})
        self.assertIn("provider unavailable", result["failing"]["error"])
        self.assertEqual(result["missing"], {"error": "Tool is not registered"})


if __name__ == "__main__":
    unittest.main()
