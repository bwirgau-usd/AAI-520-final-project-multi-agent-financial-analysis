"""Shared pytest configuration for deterministic headless test runs."""

import os

os.environ.setdefault("MPLBACKEND", "Agg")
