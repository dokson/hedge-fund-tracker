"""
Generate tests/fixtures/strategies.json — the canonical strategy definitions.

This is the single source of truth shared across the language barrier: the
Python backtest (`app/backtest/strategies.py`) and the TypeScript UI/guard
(`app/frontend/src/lib/strategies.ts`) both pin to it, so the six consensus
strategies can't be defined differently in the two implementations.

Regenerate after changing a strategy's ranking/filters:
    pipenv run python -X utf8 scripts/gen_strategy_definitions.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backtest.strategies import strategy_definitions  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "strategies.json"


def main() -> None:
    """
    Write the canonical strategy definitions to the shared fixture file.
    """
    FIXTURE.write_text(json.dumps(strategy_definitions(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {FIXTURE}")


if __name__ == "__main__":
    main()
