import unittest
from unittest.mock import MagicMock, patch

import httpx2 as httpx
from openai import AuthenticationError, BadRequestError, InternalServerError, RateLimitError
from tenacity import RetryError

from app.ai.clients.zai_client import ZaiClient

_REQUEST = httpx.Request("POST", "https://api.z.ai/api/paas/v4/chat/completions")
_PAID_MODEL = "glm-5.3-flashx"


def _refused(error_cls, status: int):
    """
    Builds the SDK error a provider raises for ``status``.
    """
    return error_cls("refused", response=httpx.Response(status, request=_REQUEST), body=None)


def _answer(text: str) -> MagicMock:
    """
    Builds a streamed completion carrying ``text``.
    """
    stream = MagicMock()
    stream.__enter__.return_value = [MagicMock(choices=[MagicMock(delta=MagicMock(content=text))])]
    return stream


class TestZaiFallback(unittest.TestCase):
    """
    A billed GLM model answers 429 when the account has no balance; the call must then fall back
    to the free model instead of failing.
    """

    def setUp(self):
        """
        Patches the SDK and sleeping, and builds a client on a billed model.
        """
        patcher = patch("app.ai.clients.base_openai_client.OpenAI")
        self.create = patcher.start().return_value.chat.completions.create
        self.addCleanup(patcher.stop)
        sleeper = patch("time.sleep")
        sleeper.start()
        self.addCleanup(sleeper.stop)
        with patch.dict("os.environ", {"ZAI_API_KEY": "test_key"}):
            self.client = ZaiClient(model=_PAID_MODEL)

    def models_asked(self) -> list[str]:
        """
        The model of every request sent, in order.
        """
        return [c.kwargs["model"] for c in self.create.call_args_list]

    def test_a_refused_billed_model_is_answered_by_the_free_one_in_the_same_call(self):
        """
        A 429 or a 5xx on the billed model is repeated on FALLBACK_MODEL, without waiting.
        """
        refusals = (_refused(RateLimitError, 429), _refused(InternalServerError, 500))
        for refusal in refusals:
            with self.subTest(status=refusal.status_code):
                self.create.reset_mock()
                self.create.side_effect = [refusal, _answer("done")]

                with patch("tenacity.nap.time.sleep") as nap:
                    response = self.client.generate_content("Hello")

                self.assertEqual(response, "done")
                self.assertEqual(self.models_asked(), [_PAID_MODEL, ZaiClient.FALLBACK_MODEL])
                nap.assert_not_called()
                self.assertEqual(self.client.model, _PAID_MODEL)

    def test_a_genuine_error_is_not_hidden_by_the_fallback(self):
        """
        A bad request or a bad key fails at once; switching model would not fix it.
        """
        errors = (_refused(BadRequestError, 400), _refused(AuthenticationError, 401))
        for error in errors:
            with self.subTest(status=error.status_code):
                self.create.reset_mock()
                self.create.side_effect = error

                with self.assertRaises(type(error)):
                    self.client.generate_content("Hello")

                self.assertEqual(self.models_asked(), [_PAID_MODEL])

    def test_the_free_model_has_nowhere_to_fall_back_to(self):
        """
        On FALLBACK_MODEL itself a 429 goes to the ordinary retry, which then gives up.
        """
        with patch.dict("os.environ", {"ZAI_API_KEY": "test_key"}):
            client = ZaiClient(model=ZaiClient.FALLBACK_MODEL)
        self.create.side_effect = _refused(RateLimitError, 429)

        with self.assertRaises(RetryError):
            client.generate_content("Hello")

        self.assertEqual(self.models_asked(), [ZaiClient.FALLBACK_MODEL] * 3)


if __name__ == "__main__":
    unittest.main()
