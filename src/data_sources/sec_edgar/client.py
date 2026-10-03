"""SEC EDGAR ingestion adapter.

This module owns SEC-specific request identification, CIK resolution, company
facts parsing, and recent-filing URL construction. Consumers receive plain
Python data and do not need to know the SEC response shape.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

SEC_DATA_BASE_URL = "https://data.sec.gov"
SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_ARCHIVES_BASE_URL = "https://www.sec.gov/Archives/edgar/data"
SUPPORTED_FORMS = frozenset({"10-K", "10-Q", "8-K"})
MAX_RECENT_FILINGS = 8

SELECTED_FACTS = {
    "Revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "USD",
    ),
    "Net Income": ("NetIncomeLoss", "USD"),
    "Operating Income": ("OperatingIncomeLoss", "USD"),
    "Operating Cash Flow": (
        "NetCashProvidedByUsedInOperatingActivities",
        "USD",
    ),
    "Assets": ("Assets", "USD"),
    "Liabilities": ("Liabilities", "USD"),
    "Stockholders Equity": ("StockholdersEquity", "USD"),
    "Diluted EPS": ("EarningsPerShareDiluted", "USD/shares"),
}


class HttpResponse(Protocol):
    """Subset of a requests response used by the adapter."""

    def raise_for_status(self) -> None:
        """Raise for an unsuccessful HTTP response."""

    def json(self) -> Any:
        """Decode the JSON response body."""


HttpGet = Callable[..., HttpResponse]


class SecEdgarClient:
    """Retrieve and normalize public company data from SEC EDGAR."""

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        http_get: HttpGet | None = None,
        timeout: float = 30,
    ) -> None:
        self._user_agent = user_agent.strip() if user_agent is not None else None
        self._http_get = http_get
        self._timeout = timeout
        self._ticker_ciks: dict[str, str] | None = None

    def get_cik(self, symbol: str) -> str:
        """Resolve a ticker to the SEC's zero-padded ten-digit CIK."""

        normalized_symbol = self._normalize_symbol(symbol)
        if self._ticker_ciks is None:
            self._ticker_ciks = self._load_ticker_ciks()

        cik = self._ticker_ciks.get(normalized_symbol)
        if cik is None:
            raise ValueError(f"SEC EDGAR CIK not found for {normalized_symbol}")
        return cik

    def get_company_data(self, symbol: str) -> dict[str, Any]:
        """Return official company facts and recent material filings."""

        normalized_symbol = self._normalize_symbol(symbol)
        cik = self.get_cik(normalized_symbol)
        companyfacts = self._get_json(
            f"{SEC_DATA_BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"
        )
        submissions = self._get_json(f"{SEC_DATA_BASE_URL}/submissions/CIK{cik}.json")

        official_facts: dict[str, dict[str, Any]] = {}
        for label, (tag, unit) in SELECTED_FACTS.items():
            latest = self._latest_fact(companyfacts, tag, unit)
            if latest is not None:
                official_facts[label] = latest

        return {
            "source": "SEC EDGAR",
            "ticker": normalized_symbol,
            "cik": cik,
            "entity_name": companyfacts.get("entityName") or submissions.get("name"),
            "sic": submissions.get("sic"),
            "sic_description": submissions.get("sicDescription"),
            "official_company_facts": official_facts,
            "recent_filings": self._recent_filings(submissions, cik),
        }

    def _load_ticker_ciks(self) -> dict[str, str]:
        ticker_payload = self._get_json(SEC_TICKER_URL)
        ticker_ciks: dict[str, str] = {}
        for item in ticker_payload.values():
            if not isinstance(item, Mapping):
                continue
            ticker = str(item.get("ticker", "")).strip().upper()
            cik_value = item.get("cik_str")
            if not ticker or cik_value is None:
                continue
            try:
                cik = str(int(cik_value)).zfill(10)
            except (TypeError, ValueError):
                continue
            ticker_ciks[ticker] = cik
        return ticker_ciks

    def _get_json(self, url: str) -> dict[str, Any]:
        user_agent = (
            self._user_agent
            if self._user_agent is not None
            else os.getenv("SEC_USER_AGENT", "").strip()
        )
        if not user_agent:
            raise RuntimeError(
                "SEC_USER_AGENT is required and should identify the application "
                "and a monitored contact email."
            )

        http_get = self._http_get
        if http_get is None:
            try:
                import requests
            except ImportError as exc:  # pragma: no cover - dependency failure
                raise RuntimeError(
                    "The requests package is required. Install project "
                    "dependencies from requirements.txt."
                ) from exc
            http_get = requests.get

        response = http_get(
            url,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json",
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise TypeError(f"SEC EDGAR returned non-object JSON for {url}")
        return dict(payload)

    @staticmethod
    def _latest_fact(
        companyfacts: Mapping[str, Any],
        tag: str,
        preferred_unit: str,
    ) -> dict[str, Any] | None:
        facts = companyfacts.get("facts")
        us_gaap = facts.get("us-gaap") if isinstance(facts, Mapping) else None
        fact = us_gaap.get(tag) if isinstance(us_gaap, Mapping) else None
        units = fact.get("units") if isinstance(fact, Mapping) else None
        if not isinstance(units, Mapping):
            return None

        selected_unit = preferred_unit
        records = units.get(preferred_unit)
        if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
            selected = next(
                (
                    (str(unit), values)
                    for unit, values in units.items()
                    if isinstance(values, Sequence)
                    and not isinstance(values, (str, bytes))
                ),
                None,
            )
            if selected is None:
                return None
            selected_unit, records = selected

        usable_records = [
            record
            for record in records
            if isinstance(record, Mapping)
            and record.get("val") is not None
            and record.get("filed")
        ]
        if not usable_records:
            return None

        latest = max(
            usable_records,
            key=lambda record: (
                str(record.get("filed", "")),
                str(record.get("end", "")),
            ),
        )
        return {
            "value": latest.get("val"),
            "unit": selected_unit,
            "fiscal_year": latest.get("fy"),
            "fiscal_period": latest.get("fp"),
            "form": latest.get("form"),
            "period_end": latest.get("end"),
            "filed": latest.get("filed"),
            "accession": latest.get("accn"),
        }

    @staticmethod
    def _recent_filings(
        submissions: Mapping[str, Any],
        cik: str,
    ) -> list[dict[str, Any]]:
        filings = submissions.get("filings")
        recent = filings.get("recent") if isinstance(filings, Mapping) else None
        if not isinstance(recent, Mapping):
            return []

        forms = _list_value(recent.get("form"))
        accessions = _list_value(recent.get("accessionNumber"))
        filing_dates = _list_value(recent.get("filingDate"))
        report_dates = _list_value(recent.get("reportDate"))
        primary_documents = _list_value(recent.get("primaryDocument"))
        recent_filings: list[dict[str, Any]] = []

        for index, form_value in enumerate(forms):
            form = str(form_value)
            if form not in SUPPORTED_FORMS:
                continue

            accession = _at(accessions, index)
            primary_document = _at(primary_documents, index)
            filing_url = None
            if accession and primary_document:
                accession_path = str(accession).replace("-", "")
                filing_url = (
                    f"{SEC_ARCHIVES_BASE_URL}/{int(cik)}/{accession_path}/"
                    f"{primary_document}"
                )

            recent_filings.append(
                {
                    "form": form,
                    "filing_date": _at(filing_dates, index),
                    "report_date": _at(report_dates, index),
                    "accession": accession,
                    "filing_url": filing_url,
                }
            )
            if len(recent_filings) >= MAX_RECENT_FILINGS:
                break

        return recent_filings

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must be a non-empty string")
        return normalized_symbol


def _list_value(value: object) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return list(value)


def _at(values: Sequence[Any], index: int) -> Any | None:
    return values[index] if index < len(values) else None
