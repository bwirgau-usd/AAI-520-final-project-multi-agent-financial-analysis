"""Composition root for the tools exposed to research agents."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from src.agents.news_agent import run_news_agent
from src.data_sources.sec_edgar import SecEdgarClient
from src.data_sources.yahoo_finance import YahooFinanceClient
from src.tools.financial_tools import (
    get_balance_sheet,
    get_cash_flow,
    get_financial_growth,
    get_financials,
    get_sec_edgar,
)
from src.tools.market_tools import get_company_info, get_price_data

Tool = Callable[[str], dict[str, Any]]


def build_yahoo_tools(
    client: YahooFinanceClient | None = None,
) -> dict[str, Tool]:
    """Bind one Yahoo Finance client to the agent-facing financial tools."""

    data_client = client if client is not None else YahooFinanceClient()
    return {
        "price_data": partial(get_price_data, data_client),
        "company_info": partial(get_company_info, data_client),
        "financials": partial(get_financials, data_client),
        "cash_flow": partial(get_cash_flow, data_client),
        "balance_sheet": partial(get_balance_sheet, data_client),
        "financial_growth": partial(get_financial_growth, data_client),
        "news": run_news_agent,
    }


def build_sec_tools(
    client: SecEdgarClient | None = None,
) -> dict[str, Tool]:
    """Bind one SEC EDGAR client to the agent-facing filings tool."""

    data_client = client if client is not None else SecEdgarClient()
    return {"sec_edgar": partial(get_sec_edgar, data_client)}


def build_tools(
    yahoo_client: YahooFinanceClient | None = None,
    sec_client: SecEdgarClient | None = None,
) -> dict[str, Tool]:
    """Assemble every production research tool in a deterministic order."""

    yahoo_tools = build_yahoo_tools(yahoo_client)
    # The production workflow executes the richer multi-source news pipeline
    # as its own observable stage. Keep the original ``news`` registry entry
    # public without running both implementations in the same research pass.
    yahoo_tools.pop("news", None)
    return {**yahoo_tools, **build_sec_tools(sec_client)}


TOOLS = build_tools()
