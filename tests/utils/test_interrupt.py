import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.utils.interrupt import install_keyboardinterrupt_filter


def _hook_spec(unraisable):
    """
    Shape-only callable used as a MagicMock spec so the spy mimics a real
    sys.unraisablehook: callable, but without auto-vivified attributes (a bare
    MagicMock would make the filter's `_kbi_filter` marker check spuriously
    truthy).
    """


def _spy_hook():
    """
    Returns a MagicMock that stands in for the previously-installed hook.
    """
    return MagicMock(spec=_hook_spec)


def _unraisable(exc_type):
    """
    Builds a stand-in for the object CPython passes to sys.unraisablehook,
    exposing only the attribute the filter inspects.
    """
    return SimpleNamespace(
        exc_type=exc_type,
        exc_value=exc_type(),
        exc_traceback=None,
        err_msg=None,
        object=None,
    )


class TestInstallKeyboardInterruptFilter(unittest.TestCase):
    def setUp(self):
        """
        Snapshots the live hook so each test starts from a clean slate.
        """
        self._saved_hook = sys.unraisablehook

    def tearDown(self):
        """
        Restores the original hook so the filter does not leak into other tests.
        """
        sys.unraisablehook = self._saved_hook

    def test_swallows_unraisable_interrupts(self):
        """
        A KeyboardInterrupt (the curl_cffi Ctrl+C case) or SystemExit escaping a
        C callback is dropped instead of being forwarded to the noisy default hook.
        """
        for exc_type in (KeyboardInterrupt, SystemExit):
            with self.subTest(exc_type=exc_type.__name__):
                previous = _spy_hook()
                sys.unraisablehook = previous

                install_keyboardinterrupt_filter()
                sys.unraisablehook(_unraisable(exc_type))

                previous.assert_not_called()

    def test_forwards_other_unraisables(self):
        """
        Genuine unraisable bugs (e.g. a ValueError in a __del__) are still
        delegated to the previous hook so they remain visible.
        """
        previous = _spy_hook()
        sys.unraisablehook = previous

        install_keyboardinterrupt_filter()
        payload = _unraisable(ValueError)
        sys.unraisablehook(payload)

        previous.assert_called_once_with(payload)

    def test_is_idempotent(self):
        """
        Installing twice must not double-wrap: a forwarded unraisable should
        reach the genuine original hook exactly once, not be relayed through a
        chain of filters.
        """
        previous = _spy_hook()
        sys.unraisablehook = previous

        install_keyboardinterrupt_filter()
        install_keyboardinterrupt_filter()
        payload = _unraisable(ValueError)
        sys.unraisablehook(payload)

        previous.assert_called_once_with(payload)


if __name__ == "__main__":
    unittest.main()
