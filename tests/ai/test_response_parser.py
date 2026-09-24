import unittest

from app.ai.response_parser import ResponseParser


class TestResponseParser(unittest.TestCase):
    """
    The JSON response parser: strict JSON first, tolerant extraction only as a fallback.
    """

    def test_parses_a_bare_json_object(self):
        """
        Provider-enforced output is a bare JSON object.
        """
        self.assertEqual(ResponseParser.parse_json('{"a": 1, "b": [1, 2]}'), {"a": 1, "b": [1, 2]})

    def test_parses_surrounding_whitespace(self):
        """
        Leading and trailing whitespace is ignored.
        """
        self.assertEqual(ResponseParser.parse_json('\n  {"a": null}  \n'), {"a": None})

    def test_parses_a_json_fence(self):
        """
        Prompt-only answers often wrap the object in a json fence.
        """
        text = 'Here you go:\n```json\n{"a": 1}\n```\nDone.'
        self.assertEqual(ResponseParser.parse_json(text), {"a": 1})

    def test_uses_the_last_fence(self):
        """
        Earlier fences may be drafts; the final one is the answer.
        """
        text = '```json\n{"a": 1}\n```\nrevised:\n```json\n{"a": 2}\n```'
        self.assertEqual(ResponseParser.parse_json(text), {"a": 2})

    def test_parses_an_object_embedded_in_prose(self):
        """
        Without a fence, the outermost braces delimit the object.
        """
        self.assertEqual(ResponseParser.parse_json('Result: {"a": {"b": 1}} end'), {"a": {"b": 1}})

    def test_invalid_json_returns_empty_dict(self):
        """
        Unparseable text yields {} so callers raise their retryable error.
        """
        with self.assertLogs("app.ai.response_parser", level="ERROR"):
            self.assertEqual(ResponseParser.parse_json('{"a": 1,'), {})

    def test_empty_text_returns_empty_dict(self):
        """
        An empty or blank response yields {}.
        """
        with self.assertLogs("app.ai.response_parser", level="ERROR"):
            self.assertEqual(ResponseParser.parse_json(""), {})
            self.assertEqual(ResponseParser.parse_json("   \n\t "), {})

    def test_non_object_json_returns_empty_dict(self):
        """
        Every response type is an object, so a top-level array or scalar is invalid.
        """
        with self.assertLogs("app.ai.response_parser", level="ERROR"):
            self.assertEqual(ResponseParser.parse_json("[1, 2]"), {})
            self.assertEqual(ResponseParser.parse_json("42"), {})

    def test_rejects_non_finite_constants(self):
        """
        NaN and Infinity are not JSON and must not reach the numeric validators.
        """
        with self.assertLogs("app.ai.response_parser", level="ERROR"):
            self.assertEqual(ResponseParser.parse_json('{"a": NaN}'), {})


if __name__ == "__main__":
    unittest.main()
