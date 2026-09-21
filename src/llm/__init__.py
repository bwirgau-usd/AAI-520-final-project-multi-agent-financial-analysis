"""Public language-model interface used by the research agents."""

from .ollama import DEFAULT_OLLAMA_MODEL, OllamaChatClient, ask_llm

__all__ = ["DEFAULT_OLLAMA_MODEL", "OllamaChatClient", "ask_llm"]

