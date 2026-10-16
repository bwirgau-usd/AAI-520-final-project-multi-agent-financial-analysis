"""Offline tests for the SEC EDGAR data-source adapter."""

import unittest
from unittest.mock import patch

from src.data_sources.sec_edgar.client import (
    SEC_DATA_BASE_URL,
    SEC_TICKER_URL,
    SecEdgarClient,
)


class FakeResponse:
    def __init__(self, payload, error=None):
        self._payload = payload
        self._error = error

    def raise_for_status(self):
        if self._error is not None:
            raise self._error

    def json(self):
        return self._payload


class FakeHttpGet:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payloads[url])


def fact_record(value, filed, *, unit="USD", end="2025-09-27"):
    return {
        "unit": unit,
        "record": {
            "val": value,
            "fy": 2025,
            "fp": "FY",
            "form": "10-K",
            "end": end,
            "filed": filed,
            "accn": "0000320193-25-000079",
        },
    }


class TestSecEdgarClient(unittest.TestCase):
    def setUp(self):
        self.cik = "0000320193"
        self.facts_url = f"{SEC_DATA_BASE_URL}/api/xbrl/companyfacts/CIK{self.cik}.json"
        self.submissions_url = f"{SEC_DATA_BASE_URL}/submissions/CIK{self.cik}.json"

    def test_retrieves_latest_official_facts_and_recent_filings(self):
        older = fact_record(100, "2024-11-01")["record"]
        latest = fact_record(125, "2025-10-31")["record"]
        eps = fact_record(6.25, "2025-10-31", unit="USD / shares")
        payloads = {
            SEC_TICKER_URL: {
                "0": {"ticker": "AAPL", "cik_str": 320193},
                "bad": {"ticker": "BAD", "cik_str": "not-a-number"},
            },
            self.facts_url: {
                "entityName": "Apple Inc.",
                "facts": {
                    "us-gaap": {
                        "RevenueFromContractWithCustomerExcludingAssessedTax": {
                            "units": {"USD": [latest, older]}
                        },
                        "EarningsPerShareDiluted": {
                            "units": {eps["unit"]: [eps["record"]]}
                        },
                    }
                },
            },
            self.submissions_url: {
                "name": "Submission Name",
                "sic": "3571",
                "sicDescription": "Electronic Computers",
                "filings": {
                    "recent": {
                        "form": ["S-8", "10-K", "8-K"],
                        "accessionNumber": [
                            "0000000000-25-000001",
                            "0000320193-25-000079",
                            "0000320193-25-000080",
                        ],
                        "filingDate": [
                            "2025-01-01",
                            "2025-10-31",
                            "2025-11-01",
                        ],
                        "reportDate": [
                            "2024-12-31",
                            "2025-09-27",
                            "2025-10-30",
                        ],
                        "primaryDocument": [
                            "ignored.htm",
                            "aapl-20250927.htm",
                            "aapl-20251030.htm",
                        ],
                    }
                },
            },
        }
        http_get = FakeHttpGet(payloads)
        client = SecEdgarClient(
            user_agent="AAI-520 Team team@example.com",
            http_get=http_get,
        )

        result = client.get_company_data(" aapl ")

        self.assertEqual(result["source"], "SEC EDGAR")
        self.assertEqual(result["ticker"], "AAPL")
        self.assertEqual(result["cik"], self.cik)
        self.assertEqual(result["entity_name"], "Apple Inc.")
        self.assertEqual(result["sic"], "3571")
        self.assertEqual(
            result["official_company_facts"]["Revenue"]["value"],
            125,
        )
        self.assertEqual(
            result["official_company_facts"]["Diluted EPS"]["unit"],
            "USD / shares",
        )
        self.assertEqual(
            [filing["form"] for filing in result["recent_filings"]],
            ["10-K", "8-K"],
        )
        self.assertEqual(
            result["recent_filings"][0]["filing_url"],
            (
                "https://www.sec.gov/Archives/edgar/data/320193/"
                "000032019325000079/aapl-20250927.htm"
            ),
        )
        for _url, kwargs in http_get.calls:
            self.assertEqual(
                kwargs["headers"]["User-Agent"],
                "AAI-520 Team team@example.com",
            )
            self.assertEqual(kwargs["headers"]["Accept"], "application/json")
            self.assertEqual(kwargs["timeout"], 30)

    def test_caches_ticker_to_cik_mapping(self):
        http_get = FakeHttpGet(
            {SEC_TICKER_URL: {"0": {"ticker": "AAPL", "cik_str": 320193}}}
        )
        client = SecEdgarClient(user_agent="Test test@example.com", http_get=http_get)

        self.assertEqual(client.get_cik("AAPL"), self.cik)
        self.assertEqual(client.get_cik("aapl"), self.cik)
        self.assertEqual(len(http_get.calls), 1)

    def test_requires_a_descriptive_user_agent(self):
        calls = []

        def unexpected_get(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("HTTP should not run without a user agent")

        client = SecEdgarClient(user_agent="", http_get=unexpected_get)

        with self.assertRaisesRegex(RuntimeError, "SEC_USER_AGENT is required"):
            client.get_cik("AAPL")
        self.assertEqual(calls, [])

    def test_reads_environment_user_agent_when_request_runs(self):
        http_get = FakeHttpGet({SEC_TICKER_URL: {}})
        with patch.dict("os.environ", {}, clear=True):
            client = SecEdgarClient(http_get=http_get)
            with (
                patch.dict(
                    "os.environ",
                    {"SEC_USER_AGENT": "Late Config config@example.com"},
                ),
                self.assertRaisesRegex(ValueError, "CIK not found"),
            ):
                client.get_cik("AAPL")

        self.assertEqual(
            http_get.calls[0][1]["headers"]["User-Agent"],
            "Late Config config@example.com",
        )

    def test_rejects_unknown_or_empty_symbols(self):
        http_get = FakeHttpGet({SEC_TICKER_URL: {}})
        client = SecEdgarClient(user_agent="Test test@example.com", http_get=http_get)

        with self.assertRaisesRegex(ValueError, "CIK not found for UNKNOWN"):
            client.get_cik("unknown")
        with self.assertRaisesRegex(ValueError, "non-empty"):
            client.get_cik("  ")

    def test_rejects_non_object_sec_json(self):
        http_get = FakeHttpGet({SEC_TICKER_URL: []})
        client = SecEdgarClient(user_agent="Test test@example.com", http_get=http_get)

        with self.assertRaisesRegex(TypeError, "non-object JSON"):
            client.get_cik("AAPL")


if __name__ == "__main__":
    unittest.main()
