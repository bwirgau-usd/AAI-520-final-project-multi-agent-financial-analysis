"""Tests for assembling the agent-facing Yahoo Finance tool registry."""

import unittest

from src.tools.registry import build_yahoo_tools


class FakeYahooFinanceClient:
    def get_history(self, symbol, period="1y"):
        return [100.0, 105.0, 110.0]

    def get_company_info(self, symbol):
        return {"longName": "Example Corp"}

    def get_income_statement(self, symbol):
        return {"Total Revenue": {"2025": 500.0}}

    def get_cash_flow_statement(self, symbol):
        return {"Free Cash Flow": {"2025": 80.0}}


class TestToolRegistry(unittest.TestCase):
    def test_builds_complete_symbol_only_tool_registry(self):
        tools = build_yahoo_tools(FakeYahooFinanceClient())

        self.assertEqual(
            list(tools),
            ["price_data", "company_info", "financials", "cash_flow"],
        )
        self.assertEqual(tools["price_data"]("AAPL")["latest_price"], 110.0)
        self.assertEqual(
            tools["company_info"]("AAPL")["longName"], "Example Corp"
        )
        self.assertEqual(
            tools["financials"]("AAPL"),
            {"Total Revenue": {"2025": 500.0}},
        )
        self.assertEqual(
            tools["cash_flow"]("AAPL"),
            {"Free Cash Flow": {"2025": 80.0}},
        )

