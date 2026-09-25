"""Opt-in integration test for the local Ollama service."""

import os

import pytest

from src.llm import ask_llm


RUN_OLLAMA_TESTS = os.getenv("RUN_OLLAMA_TESTS") == "1"


@pytest.mark.skipif(
    not RUN_OLLAMA_TESTS,
    reason="Set RUN_OLLAMA_TESTS=1 to test the local Ollama service.",
)
def test_ollama_answers_financial_prompt() -> None:
    """Confirm that the configured local model accepts and answers a prompt."""

    response = ask_llm(
        "Explain what a P/E ratio means in one sentence.",
        model=os.getenv("OLLAMA_MODEL", "llama3.2"),
    )

    assert response
