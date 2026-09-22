"""Offline end-to-end tests for the extracted research workflow."""

import json
import tempfile
import unittest
from pathlib import Path

from src.graph import build_research_workflow
from src.memory import ResearchMemoryStore


class StubLlm:
    def __init__(self):
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if "planning an evidence-based" in prompt:
            return json.dumps(
                {
                    "objectives": ["Review price and cash flow"],
                    "tools": ["price_data", "cash_flow", "not_registered"],
                    "questions": ["Is cash generation supporting performance?"],
                }
            )
        if "research quality reviewer" in prompt:
            return json.dumps(
                {
                    "strengths": ["Current market data"],
                    "weaknesses": ["No news evidence"],
                    "missing_information": ["Recent news"],
                    "suspicious_values": [],
                    "follow_up_questions": ["Can a news provider be added?"],
                }
            )
        if "Write a concise" in prompt:
            return "# Report\n\nMarket performance and cash flow are reviewed."
        if "Summarize reusable" in prompt:
            return "Add recent news evidence in a future run."
        raise AssertionError(f"Unexpected prompt: {prompt}")


class TestResearchWorkflow(unittest.TestCase):
    def test_runs_all_stages_with_injected_dependencies(self):
        tools = {
            "price_data": lambda _symbol: {
                "latest_price": 210.0,
                "1y_return_percent": 15.0,
            },
            "cash_flow": lambda _symbol: {
                "Operating Cash Flow": {"2025": 120.0},
                "Free Cash Flow": {"2025": 90.0},
            },
        }
        llm = StubLlm()
        progress = []
        with tempfile.TemporaryDirectory() as directory:
            store = ResearchMemoryStore(Path(directory) / "memory.json")
            workflow = build_research_workflow(
                llm=llm,
                tools=tools,
                memory_store=store,
            )

            result = workflow.run(" aapl ", progress=progress.append)

            self.assertEqual(result["symbol"], "AAPL")
            self.assertEqual(result["plan"]["tools"], ["price_data", "cash_flow"])
            self.assertEqual(set(result["observations"]), set(tools))
            self.assertEqual(
                result["reflection"]["strengths"],
                ["Current market data"],
            )
            self.assertIn("Report", result["report"])
            self.assertEqual(result["memory_entry"]["symbol"], "AAPL")
            self.assertEqual(len(store.for_symbol("aapl")), 1)
            self.assertTrue(progress[0].startswith("1/7"))
            self.assertTrue(progress[-1].startswith("7/7"))
            self.assertEqual(len(llm.prompts), 4)

    def test_can_skip_memory_persistence(self):
        llm = StubLlm()
        with tempfile.TemporaryDirectory() as directory:
            store = ResearchMemoryStore(Path(directory) / "memory.json")
            workflow = build_research_workflow(
                llm=llm,
                tools={"price_data": lambda _symbol: {}},
                memory_store=store,
            )

            result = workflow.run("MSFT", remember=False)

            self.assertNotIn("memory_entry", result)
            self.assertEqual(store.load(), [])
            self.assertEqual(len(llm.prompts), 3)


if __name__ == "__main__":
    unittest.main()
