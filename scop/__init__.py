"""Minimal package marker for the scop project so Poetry can install the package.

This package is intentionally minimal; it allows Poetry to create entry points
from `[project.scripts]` when the project is installed into the virtualenv.
"""

__version__ = "0.1.2"
