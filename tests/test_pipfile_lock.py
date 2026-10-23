"""
Pipfile platform markers must survive into Pipfile.lock: Dependabot's relocks have
replaced them with the package's requires-python, and `pipenv sync` then tried to
build uvloop on Windows.
"""

import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = {"packages": "default", "dev-packages": "develop"}


class LockMarkersTest(unittest.TestCase):
    """
    Every marker declared in the Pipfile is the marker of the locked entry.
    """

    def test_locked_entries_keep_the_pipfile_markers(self):
        """
        A package restricted by platform in the Pipfile is restricted the same way in the lock.
        """
        with (ROOT / "Pipfile").open("rb") as pipfile:
            declared = tomllib.load(pipfile)
        lock = json.loads((ROOT / "Pipfile.lock").read_text(encoding="utf-8"))
        checked = 0
        for pipfile_section, lock_section in SECTIONS.items():
            for name, spec in declared.get(pipfile_section, {}).items():
                if not isinstance(spec, dict) or "markers" not in spec:
                    continue
                checked += 1
                with self.subTest(package=name):
                    self.assertEqual(lock[lock_section][name].get("markers"), spec["markers"])
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
