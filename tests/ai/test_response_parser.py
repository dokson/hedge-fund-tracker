import unittest
from app.ai.response_parser import ResponseParser

class TestResponseParser(unittest.TestCase):
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


    def test_extract_and_decode_with_generic_markdown(self):
        """
        Tests parsing a TOON string enclosed in generic ``` ... ``` markdown.
        """
        response_text = '```\nnested:\n  inner_key: 42\n```'
        expected = {'nested': {'inner_key': 42}}
        self.assertEqual(ResponseParser.extract_and_decode_toon(response_text), expected)


    def test_extract_and_decode_with_leading_text(self):
        """
        Tests that text before the TOON block is ignored and does not cause a parsing error.
        """
        response_text = 'Here is the TOON data:\nkey: "value"'
        expected = {'key': 'value'}
        self.assertEqual(ResponseParser.extract_and_decode_toon(response_text), expected)


    def test_extract_and_decode_with_leading_text_and_colon(self):
        """
        Tests that text before the TOON block containing a colon is ignored.
        """
        response_text = 'Here is the TOON data as requested:\nkey: "value"'
        expected = {'key': 'value'}
        self.assertEqual(ResponseParser.extract_and_decode_toon(response_text), expected)


    def test_extract_and_decode_invalid_toon(self):
        """
        Tests that an invalid TOON string (unquoted hyphen in key) returns an empty dictionary.
        """
        response_text = 'invalid-key: "value"'
        self.assertEqual(ResponseParser.extract_and_decode_toon(response_text), {})


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


    def test_extract_and_decode_no_toon_found(self):
        """
        Tests that a string without a plausible TOON start returns an empty dictionary.
        """
        response_text = '--- no data here ---'
        self.assertEqual(ResponseParser.extract_and_decode_toon(response_text), {})


if __name__ == '__main__':
    unittest.main()
