import unittest
from app.ai.response_parser import ResponseParser

class TestResponseParser(unittest.TestCase):
    def test_comment_with_quote(self):
        """
        Tests stripping a comment that contains a quote, which previously caused 'Unterminated string' error.
        """
        response_text = """
```toon
ticker: "Q"
sub_industry: "Semiconductors"  # Assumed based on "Qnity Electronics Inc" description
```
"""
        expected = {'ticker': 'Q', 'sub_industry': 'Semiconductors'}
        result = ResponseParser.extract_and_decode_toon(response_text)
        self.assertEqual(result, expected)


    def test_hash_inside_string(self):
        """
        Tests that a hash symbol inside a quoted string is NOT stripped as a comment.
        """
        response_text = """
```toon
ticker: "NVDA"
description: "This is item # 1 in the list"
```
"""
        expected = {'ticker': 'NVDA', 'description': 'This is item # 1 in the list'}
        result = ResponseParser.extract_and_decode_toon(response_text)
        self.assertEqual(result, expected)


    def test_extract_and_decode_simple_toon(self):
        """
        Tests parsing a simple, valid TOON string.
        """
        response_text = 'key1: "value1"\nkey2: 123\nbool_key: true'
        expected = {'key1': 'value1', 'key2': 123, 'bool_key': True}
        self.assertEqual(ResponseParser.extract_and_decode_toon(response_text), expected)


    def test_extract_and_decode_with_toon_markdown(self):
        """
        Tests parsing a TOON string enclosed in ```toon ... ``` markdown.
        """
        response_text = '```toon\nkey: "value"\n```'
        expected = {'key': 'value'}
        self.assertEqual(ResponseParser.extract_and_decode_toon(response_text), expected)


    def test_extract_and_decode_with_split_markdown_tag(self):
        """
        Tests parsing a TOON string where 'toon' is on the next line after backticks.
        E.g. ```\ntoon
        """
        response_text = '```\ntoon\nkey: "value"\n```'
        expected = {'key': 'value'}
        self.assertEqual(ResponseParser.extract_and_decode_toon(response_text), expected)


    def test_extract_and_decode_with_generic_markdown(self):
        """
        Tests parsing a TOON string enclosed in generic ``` ... ``` markdown.
        """
        response_text = '```\nnested:\n  inner_key: 42\n```'
        expected = {'nested': {'inner_key': 42}}
        self.assertEqual(ResponseParser.extract_and_decode_toon(response_text), expected)




    def test_extract_and_decode_with_quoted_keys(self):
        """
        Tests parsing TOON where keys are quoted (required for special characters).
        """
        response_text = '"BRK-B": 500\n"BF.B": 200'
        expected = {'BRK-B': 500, 'BF.B': 200}
        self.assertEqual(ResponseParser.extract_and_decode_toon(response_text), expected)

    def test_extract_and_decode_empty_or_whitespace_string(self):
        """
        Tests that an empty string returns an empty dictionary.
        """
        self.assertEqual(ResponseParser.extract_and_decode_toon(''), {})
        self.assertEqual(ResponseParser.extract_and_decode_toon('   \n \t '), {})


    def test_checklist_with_yaml_list(self):
        """
        Tests filtering out YAML-style list items (bullets) that corrupt the TOON block.
        """
        response_text = """
```toon
checklist:
  - "Step 1"
  - "Step 2"
ticker: "NVDA"
company: "NVIDIA"
```
"""
        expected = {'checklist': {}, 'ticker': 'NVDA', 'company': 'NVIDIA'}
        self.assertEqual(ResponseParser.extract_and_decode_toon(response_text), expected)


    def test_checklist_with_json_list(self):
        """
        Tests filtering out JSON-style list items that don't match the TOON key-value regex.
        Note: The regex filters line-by-line, so the checklist key remains but items are dropped.
        """
        response_text = """
```toon
checklist: [
  "Step 1",
  "Step 2"
]
ticker: "NVDA"
```
"""
        # checklist: [ matches key regex?
        # checklist matches key. [ matches value start?
        # My regex: (?:\s+(?:[\d\."'\[\{]|true|false|null))
        # [ is in the character class. So "checklist: [" IS matched and kept!
        # "Step 1", line is NOT matched (no colon, no value part validation?).
        # ] line is brackets.
        # If toon.decode handles "checklist: [" followed by "ticker: ...", we get {'checklist': '[', 'ticker': ...}
        # Let's see what happens.
        result = ResponseParser.extract_and_decode_toon(response_text)
        self.assertEqual(result.get('ticker'), 'NVDA')
        # We don't strictly care about the checklist value, just that parsing succeeded.
        self.assertIn('checklist', result)


    def test_extract_last_toon_block(self):
        """
        Tests that only the LAST toon block is used if multiple blocks are present.
        This handles iterative reasoning where intermediate blocks are generated.
        """
        response_text = """
Some initial reasoning...
```toon
score: 0.5
status: "intermediate"
```

More thoughts and corrections:
```toon
score: 0.85
status: "final"
```
Final conclusion.
"""
        expected = {'score': 0.85, 'status': 'final'}
        result = ResponseParser.extract_and_decode_toon(response_text)
        self.assertEqual(result, expected)
