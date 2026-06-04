"""RFC 5424 (The Syslog Protocol) reference document renderer.

Produces RFC5424.md at the repository root using the shared RFC7841.md.j2
template. All document content is loaded from static/META5424.yaml.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from scop.rfc.base import BaseRFC


class RFC5424(BaseRFC):
    """RFC 5424 reference document model.

    Structural constraints only — all content (terms, principles, sections,
    references) is provided via static/META5424.yaml. The Conformance section
    is omitted because RFC 5424 uses no SCOP conformance block.
    """

    conformance_partial: str = ""


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent
    templates_dir = repo_root / "static" / "templates"

    env = Environment(
        loader=FileSystemLoader([str(templates_dir), str(repo_root / "static")]),
        autoescape=select_autoescape(enabled_extensions=()),
        keep_trailing_newline=True,
    )

    meta_path = repo_root / "static" / "META5424.yaml"
    raw: Any = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    model = RFC5424.model_validate(raw)

    template = env.get_template("RFC7841.md.j2")
    rendered = template.render(model.model_dump())

    out_path = repo_root / "RFC5424.md"
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
