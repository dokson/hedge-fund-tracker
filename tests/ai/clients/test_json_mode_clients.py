import unittest
from unittest.mock import MagicMock, patch

from app.ai.clients.ollama_client import OllamaClient
from app.ai.clients.zai_client import ZaiClient

_SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "integer"}},
    "required": ["score"],
    "additionalProperties": False,
}


class TestJsonModeClients(unittest.TestCase):
    """
    Ollama Cloud accepts a strict json_schema but does not apply it (models answer with their own
    keys inside a code fence), and Z.AI documents only plain JSON mode. A schema request to either
    must therefore carry the schema in the prompt.
    """

    @patch("app.ai.clients.base_openai_client.OpenAI")
    def test_schema_request_puts_the_schema_in_the_prompt_and_asks_for_json_mode(self, mock_openai):
        """
        The schema reaches the model as text, with plain JSON mode as the only server-side hint.
        """
        clients = ((OllamaClient, "OLLAMA_API_KEY"), (ZaiClient, "ZAI_API_KEY"))
        for client_cls, env_key in clients:
            with self.subTest(client=client_cls.__name__):
                create = mock_openai.return_value.chat.completions.create
                create.reset_mock()
                create.return_value.__enter__.return_value = [
                    MagicMock(choices=[MagicMock(delta=MagicMock(content='{"score": 7}'))])
                ]
                with patch.dict("os.environ", {env_key: "test_key"}):
                    client = client_cls()

                client.generate_content("Rate AAPL.", response_schema=_SCHEMA)

                kwargs = create.call_args.kwargs
                self.assertEqual(kwargs["response_format"], {"type": "json_object"})
                prompt = kwargs["messages"][0]["content"]
                self.assertIn("Rate AAPL.", prompt)
                self.assertIn('"required": [\n    "score"\n  ]', prompt)


if __name__ == "__main__":
    unittest.main()
