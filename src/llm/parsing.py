"""Utilities for parsing structured content returned by language models."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any


def parse_json_object(
    response: str,
    *,
    fallback: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract a JSON object from plain text, a code fence, or surrounding prose.

    Model responses are not always perfectly formatted. This parser accepts the
    common variations while rejecting arrays and malformed objects. A fresh copy
    of ``fallback`` is returned when no object can be decoded.
    """

    default = dict(fallback or {})
    if not isinstance(response, str) or not response.strip():
        return default

    candidates = [response.strip()]
    candidates.extend(
        match.strip()
        for match in re.findall(
            r"```(?:json)?\s*(.*?)```",
            response,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )

    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            for index, character in enumerate(candidate):
                if character != "{":
                    continue
                try:
                    parsed, _ = decoder.raw_decode(candidate[index:])
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    return parsed
            continue
        if isinstance(parsed, dict):
            return parsed

    return default
