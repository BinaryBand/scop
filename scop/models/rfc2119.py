from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
)

_Category = Literal["Draft", "Proposed Standard", "Standard"]
_Shortname = Annotated[str, Field(pattern=r"^[A-Z0-9]+$")]
_Version = Annotated[str, Field(pattern=r"^\d+(\.\d+)*$")]


class RFC2119(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str
    working_group: str
    shortname: _Shortname
    version_no: _Version
    status: _Category
    license: str = "CC0 1.0 Universal (Public Domain)"

    terms: dict[str, str] = {
        "Producer": "a SCOP-conforming CLI application that emits events.",
        "Consumer": "software that reads a SCOP event stream and renders it.",
        "Event": "a single NDJSON line emitted by a producer.",
        "Stream": "the ordered sequence of events from one command invocation.",
        "MSGID": "a string identifier classifying an event by its data type (§7).",
        "Room": "a page context derived from the subcommand path (§6).",
        "Page": "a GUI display unit corresponding to one room, assembled from one or more streams.",
        "Slot": "a named region in a page layout; events are routed to slots by MSGID family.",
    }

    principles: dict[str, str] = {
        "CLI first": "`msg` MUST always be a complete, human-readable line",
        "Standard-grounded": "SCOP MUST NOT conflict with POSIX or GNU; it defers to them",
        "Data-typed": "MSGIDs name the data type, not the display form",
        "Rooms derived": "Room is always derived from the command path — never declared",
        "Zero app knowledge": "A consumer MUST build any page from the stream alone",
        "Additive": "Consumers MUST ignore unknown MSGIDs and fields",
    }

    sections: list[RFC2119Section] = []

    @computed_field
    @property
    def identifier(self) -> str:
        return f"{self.shortname}-v{self.version}"

    @computed_field
    @property
    def version(self) -> str:
        if self.status == "Draft":
            return self.version_no + "-draft"
        return self.version_no


class RFC2119Section(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str


# --- testing ---

_MODEL = RFC2119(
    title="Structured CLI Output Protocol (SCOP)",
    working_group="Independent",
    shortname="SCOP",
    version_no="0.1.2",
    status="Draft",
    sections=[
        RFC2119Section(title="Foundation Standards"),
        RFC2119Section(title="Wire Format"),
        RFC2119Section(title="Room Model"),
        RFC2119Section(title="Event Vocabulary"),
        RFC2119Section(title="GNU Flag Contract"),
        RFC2119Section(title="Page Template"),
        RFC2119Section(title="Auto-Translation Rules"),
    ],
)


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent
    templates_dir = repo_root / "static" / "templates"

    env = Environment(
        loader=FileSystemLoader([str(templates_dir), str(repo_root / "static")]),
        autoescape=select_autoescape(enabled_extensions=()),
        keep_trailing_newline=True,
    )

    tpl_name = "RFC2119.md.j2"
    out_path = repo_root / tpl_name[: -len(".j2")]

    template = env.get_template(tpl_name)
    rendered = template.render(_MODEL.model_dump())

    out_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote: {out_path}")

    npx = shutil.which("npx")
    if npx is None:
        print("prettier: npx not found, skipping format step", file=sys.stderr)
        return 0

    result = subprocess.run(
        [npx, "--yes", "prettier", "--write", str(out_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"prettier: {result.stderr.strip()}", file=sys.stderr)
        return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
