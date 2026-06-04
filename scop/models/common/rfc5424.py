"""Pydantic model for RFC 5424 (The Syslog Protocol) document generation.

Renders RFC5424.md at the repository root using the shared RFC7841.md.j2
template. Content is drawn from static/META5424.yaml; RFC 5424 has no
SCOP-style Conformance section, so conformance_partial is set to "".
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from scop.models.common.base import BaseRFC


class RFC5424(BaseRFC):
    conformance_partial: str = ""

    terms: dict[str, str] = {
        "SYSLOG-MSG": "a complete syslog message following the RFC 5424 ABNF definition.",
        "HEADER": "the structured prefix containing PRI, VERSION, TIMESTAMP, HOSTNAME, APP-NAME, PROCID, and MSGID.",
        "PRI": "the Priority value, encoding Facility and Severity as (Facility × 8) + Severity.",
        "Facility": "a numeric code (0–23) indicating the type of process generating the message.",
        "Severity": "an importance level (0–7) from EMERG to DEBUG, as defined in this document.",
        "STRUCTURED-DATA": "optional field providing machine-parseable key-value pairs.",
        "SD-ELEMENT": "a named collection of PARAM-NAME / PARAM-VALUE pairs within STRUCTURED-DATA.",
        "MSG": "the free-form UTF-8 log line; mapped to the `msg` field in SCOP.",
    }

    principles: dict[str, str] = {
        "Layered": "Separates message content from transport; any transport mapping may be used",
        "Extensible": "Vendor-specific extensions are supported via STRUCTURED-DATA SD-IDs",
        "Structured": "SD-ELEMENTs provide machine-parseable data alongside free-form MSG",
        "Transport-independent": "Message format is defined independently of any specific transport protocol",
        "Backwards-compatible": "Inspired by BSD syslog (RFC 3164) while providing a Standards-Track format",
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    templates_dir = repo_root / "static" / "templates"

    env = Environment(
        loader=FileSystemLoader([str(templates_dir), str(repo_root / "static")]),
        autoescape=select_autoescape(enabled_extensions=()),
        keep_trailing_newline=True,
    )

    tpl_name = "RFC7841.md.j2"
    out_path = repo_root / "RFC5424.md"

    meta_path = repo_root / "static" / "META5424.yaml"
    raw: Any = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    model = RFC5424.model_validate(raw)

    template = env.get_template(tpl_name)
    rendered = template.render(model.model_dump())

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
