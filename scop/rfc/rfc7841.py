from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from scop.rfc.base import BaseRFC, RFCSection
from scop.template import _build_flags_table, _build_severity_rows

# Backward-compatibility alias for existing imports
RFC7841Section = RFCSection


class RFC7841(BaseRFC):
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


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent
    templates_dir = repo_root / "static" / "templates"

    env = Environment(
        loader=FileSystemLoader([str(templates_dir), str(repo_root / "static")]),
        autoescape=select_autoescape(enabled_extensions=()),
        keep_trailing_newline=True,
    )

    tpl_name = "RFC7841.md.j2"
    out_path = repo_root / tpl_name[: -len(".j2")]

    meta_path = repo_root / "static" / "META.yaml"
    raw: Any = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    model = RFC7841.model_validate(raw)

    north_star_path = repo_root / "static" / "NORTH_STAR.yaml"
    if north_star_path.exists():
        ns = yaml.safe_load(north_star_path.read_text(encoding="utf-8"))
        model.north_star = ns

    template = env.get_template(tpl_name)
    context = {
        **model.model_dump(),
        "severity_rows": _build_severity_rows(model.north_star),
        "flags_table": _build_flags_table(model.north_star),
    }
    rendered = template.render(context)

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
