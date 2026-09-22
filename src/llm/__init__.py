"""Public language-model interface used by the research agents."""

from .ollama import DEFAULT_OLLAMA_MODEL, OllamaChatClient, ask_llm
from .parsing import parse_json_object

__all__ = [
    "DEFAULT_OLLAMA_MODEL",
    "OllamaChatClient",
    "ask_llm",
    "parse_json_object",
]
