"""Shared contracts and utilities for external data-source adapters.

Provider-specific authentication, requests, response parsing, and error
translation belong in the corresponding provider package. Domain tools should
consume normalized adapter output rather than importing provider SDKs directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

Statement = dict[str, dict[str, float | None]]


@dataclass(frozen=True)
class PricePoint:
    """One normalized closing-price observation."""

    date: datetime
    close: float
