"""
Pre-push helper: run pyright, mypy and the unit-test suite through the
project's pipenv venv.

Resolves pipenv even when it is not on PATH. This is the reason these checks
were historically left out of the pre-commit hooks: a bare `python -m pipenv`
often resolves to the *project venv* interpreter (which has no pipenv module),
so it cannot launch pipenv. This script probes several invocations and uses the
first that works, then runs both type-checkers exactly as CI does. It exits
non-zero if either fails, so the git pre-push hook blocks the push.

Both checkers always run (the script does not stop at the first failure) so a
single push surfaces every type error at once.

This module is a *bootstrap*: the pre-push hook launches it with whatever
`python` is on PATH, which is not the project venv and may be older than the
project's own Python. It must therefore parse on those interpreters, so it
stays on conservative syntax and is excluded from the formatter's py314
rewrites in pyproject.toml. Keep it dependency-free and stdlib-only.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

_PIPFILE = Path(__file__).resolve().parents[1] / "Pipfile"

# Silence pipenv's "running within a virtual environment" courtesy notice so the
# hook output stays focused on the checker results.
_ENV = {**os.environ, "PIPENV_VERBOSITY": "-1"}


def _project_python_version(pipfile: Path = _PIPFILE) -> str | None:
    """
    Return the `python_version` declared in `pipfile`, or None if unreadable.

    Read rather than hardcoded: a stale pin makes the versioned launcher
    candidate fall through silently, so the hook quietly stops running the
    checks CI runs.
    """
    try:
        content = pipfile.read_text(encoding="utf-8")
    except OSError:
        return None

    match = re.search(r'^\s*python_version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    return match.group(1) if match else None


def _pipenv_candidates(pipfile: Path = _PIPFILE) -> list[list[str]]:
    """
    Return pipenv invocations to try, most-to-least conventional.

    The Windows launcher fallbacks handle the common case where `python` is the
    project venv, which has no pipenv installed inside it.
    """
    candidates: list[list[str]] = [["pipenv"], ["python", "-m", "pipenv"]]

    version = _project_python_version(pipfile)
    if version is not None:
        candidates.append(["py", f"-{version}", "-m", "pipenv"])
    candidates.append(["py", "-m", "pipenv"])

    return candidates


# Mirrors the commands in .github/workflows/lint.yml and run-tests.yml.
_CHECKS: list[tuple[str, list[str]]] = [
    ("pyright", ["run", "pyright"]),
    ("mypy", ["run", "mypy", "app", "database", "scripts"]),
    ("unittest", ["run", "python", "-m", "unittest", "discover"]),
]


def _resolve_pipenv() -> list[str] | None:
    """
    Return the first pipenv invocation whose `--version` succeeds, or None.
    """
    for base in _pipenv_candidates():
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
            f"{', '.join(' '.join(c) for c in _pipenv_candidates())}).\n"
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

    print("pre-push: pyright + mypy + unittest clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
