"""Pytest session hooks to auto-run ruff formatting and fixes before tests.

This helps catch low-hanging formatting/lint issues by auto-applying them
before the test suite runs.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _run_cmd(cmd: list[str], cwd: Path | None = None) -> tuple[int | None, str]:
    try:
        cp = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            cwd=cwd,
        )
        return cp.returncode, cp.stdout
    except FileNotFoundError:
        return None, ""


def pytest_sessionstart(session) -> None:  # pragma: no cover - test helper
    root = Path.cwd()

    if ruff_path := shutil.which("ruff"):
        _run_cmd([ruff_path, "format", str(root)], cwd=root)
        _run_cmd([ruff_path, "check", str(root), "--fix"], cwd=root)

    if ty_path := shutil.which("ty"):
        _run_cmd([ty_path, "check", str(root), "--fix"], cwd=root)
