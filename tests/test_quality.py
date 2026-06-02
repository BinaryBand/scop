import shutil
import subprocess
import sys

import pytest


def _run(cmd, cwd=None):
    """Run a command and return CompletedProcess with captured output."""
    try:
        return subprocess.run(cmd, shell=False, cwd=cwd, capture_output=True, text=True)
    except OSError:
        pytest.skip()


def _ensure_tool(name):
    if shutil.which(name) is None:
        print(f"Tool '{name}' not found; skipping test.", file=sys.stderr)
        pytest.skip()


def test_ruff_check():
    _ensure_tool("ruff")
    # Lint check across repository
    cp = _run([sys.executable, "-m", "ruff", "check", "."])
    assert cp.returncode == 0, "ruff found linting issues"


def test_ruff_format_check():
    _ensure_tool("ruff")
    # Formatting check
    cp = _run([sys.executable, "-m", "ruff", "format", "--check", "."])
    assert cp.returncode == 0, "ruff format check failed (run `ruff format .`)"


def test_type_check():
    _ensure_tool("ty")
    # Type check across repository
    cp = _run([sys.executable, "-m", "ty", "."])
    assert cp.returncode == 0, "Type checker found issues"
