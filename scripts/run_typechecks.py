"""
Pre-push helper: run pyright and mypy through the project's pipenv venv.

Resolves pipenv even when it is not on PATH. This is the reason these checks
were historically left out of the pre-commit hooks: a bare `python -m pipenv`
often resolves to the *project venv* interpreter (which has no pipenv module),
so it cannot launch pipenv. This script probes several invocations and uses the
first that works, then runs both type-checkers exactly as CI does. It exits
non-zero if either fails, so the git pre-push hook blocks the push.

Both checkers always run (the script does not stop at the first failure) so a
single push surfaces every type error at once.
"""

from __future__ import annotations

import os
import subprocess
import sys

# Silence pipenv's "running within a virtual environment" courtesy notice so the
# hook output stays focused on the checker results.
_ENV = {**os.environ, "PIPENV_VERBOSITY": "-1"}

# Candidate ways to invoke pipenv, most-to-least conventional. The Windows
# launcher fallback handles the common case where `python` is the project venv
# (no pipenv installed inside it).
_PIPENV_CANDIDATES: list[list[str]] = [
    ["pipenv"],
    ["python", "-m", "pipenv"],
    ["py", "-3.13", "-m", "pipenv"],
]

# Mirrors the commands in .github/workflows/lint.yml.
_CHECKS: list[tuple[str, list[str]]] = [
    ("pyright", ["run", "pyright"]),
    ("mypy", ["run", "mypy", "app", "database", "scripts"]),
]


def _resolve_pipenv() -> list[str] | None:
    """
    Return the first pipenv invocation whose `--version` succeeds, or None.
    """
    for base in _PIPENV_CANDIDATES:
        try:
            result = subprocess.run(
                [*base, "--version"],
                capture_output=True,
                check=False,
                env=_ENV,
            )
        except (FileNotFoundError, OSError):
            continue
        if result.returncode == 0:
            return base
    return None


def main() -> int:
    """
    Run pyright and mypy via pipenv; return 0 only if both pass.
    """
    pipenv = _resolve_pipenv()
    if pipenv is None:
        print(
            "pre-push: could not locate pipenv (tried: "
            f"{', '.join(' '.join(c) for c in _PIPENV_CANDIDATES)}).\n"
            "Install pipenv or run pyright/mypy manually before pushing.",
            file=sys.stderr,
        )
        return 1

    failed: list[str] = []
    for name, args in _CHECKS:
        print(f"pre-push: running {name}...", flush=True)
        result = subprocess.run([*pipenv, *args], check=False, env=_ENV)
        if result.returncode != 0:
            failed.append(name)

    if failed:
        print(f"pre-push: {', '.join(failed)} failed — push aborted.", file=sys.stderr)
        return 1

    print("pre-push: pyright + mypy clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
