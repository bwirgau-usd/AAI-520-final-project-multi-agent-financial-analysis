"""Tests for tolerant parsing of structured model responses."""

import unittest

from src.llm import parse_json_object


class TestParseJsonObject(unittest.TestCase):
    def test_parses_plain_fenced_and_embedded_objects(self):
        expected = {"tools": ["price_data"]}

        self.assertEqual(parse_json_object('{"tools": ["price_data"]}'), expected)
        self.assertEqual(
            parse_json_object('```json\n{"tools": ["price_data"]}\n```'),
            expected,
        )
        self.assertEqual(
            parse_json_object('Result: {"tools": ["price_data"]} done.'),
            expected,
        )

    def test_returns_a_copy_of_fallback_for_invalid_content(self):
        fallback = {"tools": []}

        result = parse_json_object("not json", fallback=fallback)

        self.assertEqual(result, fallback)
        self.assertIsNot(result, fallback)


if __name__ == "__main__":
    unittest.main()
