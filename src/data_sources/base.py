"""Shared contracts and utilities for external data-source adapters.

Provider-specific authentication, requests, response parsing, and error
translation belong in the corresponding provider package. Domain tools should
consume normalized adapter output rather than importing provider SDKs directly.
"""


Statement = dict[str, dict[str, float | None]]
