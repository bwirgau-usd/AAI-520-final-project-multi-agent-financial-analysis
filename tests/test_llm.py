"""Unit tests for the Ollama adapter that do not call a live model."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.llm import ask_llm


class FakeOllamaClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat(self, *, model, messages):
        self.calls.append({"model": model, "messages": messages})
        return self.response


class TestAskLlm(unittest.TestCase):
    def test_sends_prompt_and_returns_mapping_response(self):
        client = FakeOllamaClient(
            {"message": {"content": "  A concise response.  "}}
        )

        result = ask_llm("Explain P/E.", model="test-model", client=client)

        self.assertEqual(result, "A concise response.")
        self.assertEqual(
            client.calls,
            [
                {
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "Explain P/E."}],
                }
            ],
        )

    def test_accepts_object_response_and_environment_model(self):
        response = SimpleNamespace(
            message=SimpleNamespace(content="Object response")
        )
        client = FakeOllamaClient(response)

        with patch.dict(os.environ, {"OLLAMA_MODEL": "environment-model"}):
            result = ask_llm("Prompt", client=client)

        self.assertEqual(result, "Object response")
        self.assertEqual(client.calls[0]["model"], "environment-model")

    def test_rejects_blank_prompt(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            ask_llm("   ", client=FakeOllamaClient({}))

    def test_rejects_empty_response(self):
        client = FakeOllamaClient({"message": {"content": ""}})

        with self.assertRaisesRegex(RuntimeError, "empty or unsupported"):
            ask_llm("Prompt", client=client)

