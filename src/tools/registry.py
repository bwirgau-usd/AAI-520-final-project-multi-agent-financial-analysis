"""Composition root for the tools exposed to research agents."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from src.data_sources.sec_edgar import SecEdgarClient
from src.data_sources.yahoo_finance import YahooFinanceClient
from src.tools.financial_tools import get_cash_flow, get_financials, get_sec_edgar
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

    return {
        **build_yahoo_tools(yahoo_client),
        **build_sec_tools(sec_client),
    }


TOOLS = build_tools()
