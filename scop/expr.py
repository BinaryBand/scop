"""Render RFC2119.md.j2 from a pre-populated RFC2119 model instance."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from scop.models.rfc2119 import RFC2119

_MODEL = RFC2119(
    title="Structured CLI Output Protocol (SCOP)",
    working_group="Independent",
    shortname="SCOP",
    version_no="0.1.2",
    status="Draft",
)


def render() -> int:
    repo_root = Path(__file__).resolve().parent.parent
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


def main() -> int:
    return render()


if __name__ == "__main__":
    raise SystemExit(main())
