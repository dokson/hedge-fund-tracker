import json
import unittest
from pathlib import Path

from app.backtest.strategies import strategy_definitions

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "strategies.json"


class TestStrategyDefinitionsFixture(unittest.TestCase):
    """
    Guard: the Python strategy specs must match the shared canonical fixture.

    The TypeScript ``src/lib/strategies.ts`` guard pins to the same file, so the
    two implementations cannot silently diverge. Regenerate after an intentional
    change with ``pipenv run python scripts/gen_strategy_definitions.py``.
    """

    def test_matches_shared_fixture(self):
        """
        strategy_definitions() reproduces tests/fixtures/strategies.json.
        """
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(
            strategy_definitions(),
            expected,
            "Python strategies drifted from the shared fixture — regenerate with "
            "scripts/gen_strategy_definitions.py and update src/lib/strategies.ts.",
        )


if __name__ == "__main__":
    unittest.main()
