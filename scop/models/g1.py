"""Pydantic models for TLDP ABS Appendix G.1 — Standard Command-Line Options.

Models the loose standard for command-line option flag meanings documented at
https://tldp.org/LDP/abs/html/standard-options.html, covering both the
widely-accepted options and the context-dependent ones.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OptionCategory = Literal["universal", "common", "context_dependent"]


class StandardOption(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    long: str | None = Field(None, description="Long form flag (e.g. --help)")
    short: list[str] = Field(description="Short form flag(s) (e.g. ['-h'])")
    label: str = Field(description="Conventional name (e.g. 'Help')")
    description: str = Field(description="Behaviour as stated in the standard")
    category: OptionCategory = Field(
        description=(
            "universal: the two most widely-accepted options; "
            "common: other common options; "
            "context_dependent: meaning varies by program"
        )
    )
    context: str | None = Field(
        None,
        description="Programs or contexts where this meaning applies (context_dependent only)",
    )


G1_OPTIONS: list[StandardOption] = [
    StandardOption(
        short=["-h"],
        long="--help",
        label="Help",
        description="Give usage message and exit.",
        category="universal",
    ),
    StandardOption(
        short=["-v"],
        long="--version",
        label="Version",
        description="Show program version and exit.",
        category="universal",
    ),
    StandardOption(
        short=["-a"],
        long="--all",
        label="All",
        description="Show all information or operate on all arguments.",
        category="common",
    ),
    StandardOption(
        short=["-l"],
        long="--list",
        label="List",
        description="List files or arguments without taking other action.",
        category="common",
    ),
    StandardOption(
        short=["-o"],
        long=None,
        label="Output",
        description="Output filename follows.",
        category="common",
    ),
    StandardOption(
        short=["-q"],
        long="--quiet",
        label="Quiet",
        description="Suppress stdout.",
        category="common",
    ),
    StandardOption(
        short=["-r", "-R"],
        long="--recursive",
        label="Recursive",
        description="Operate recursively (down directory tree).",
        category="common",
    ),
    StandardOption(
        short=["-v"],
        long="--verbose",
        label="Verbose",
        description="Output additional information to stdout or stderr.",
        category="common",
    ),
    StandardOption(
        short=["-z"],
        long="--compress",
        label="Compress",
        description="Apply compression (usually gzip).",
        category="common",
    ),
    StandardOption(
        short=["-f"],
        long="--file",
        label="File",
        description="Filename follows.",
        category="context_dependent",
        context="tar, gawk",
    ),
    StandardOption(
        short=["-f"],
        long="--force",
        label="Force",
        description="Force overwrite of target file(s).",
        category="context_dependent",
        context="cp, mv, rm",
    ),
]
