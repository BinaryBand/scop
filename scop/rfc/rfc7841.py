from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from scop.rfc.base import BaseRFC
from scop.template import _build_flags_table, _build_severity_rows


class RFC7841(BaseRFC):
    """SCOP specification document, rendered using RFC 7841 boilerplate.

    All document content (terms, principles, sections, references) is loaded
    from static/META.yaml. This class enforces only structural constraints
    inherited from BaseRFC.
    """


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

    meta_path = repo_root / "static" / "METASCOP.yaml"
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
