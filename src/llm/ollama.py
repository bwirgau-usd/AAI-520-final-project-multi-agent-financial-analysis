"""Ollama client adapter."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any, Protocol


DEFAULT_OLLAMA_MODEL = "llama3.2:latest"


class OllamaChatClient(Protocol):
    """Structural type for the part of the Ollama client that we use."""

    def chat(self, *, model: str, messages: list[dict[str, str]]) -> Any:
        """Send chat messages to an Ollama model."""


def ask_llm(
    prompt: str,
    *,
    model: str | None = None,
    client: OllamaChatClient | None = None,
) -> str:
    """Send one user prompt to Ollama and return its non-empty text response."""

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    if client is None:
        try:
            import ollama
        except ImportError as exc:  # pragma: no cover - dependency failure
            raise RuntimeError(
                "The ollama package is required. Install project dependencies "
                "from requirements.txt."
            ) from exc
        client = ollama

    response = client.chat(
        model=model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        messages=[{"role": "user", "content": prompt}],
    )

    if isinstance(response, Mapping):
        message = response.get("message")
    else:
        message = getattr(response, "message", None)

    if isinstance(message, Mapping):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)

    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Ollama returned an empty or unsupported response.")

    return content.strip()

