"""Render Jinja2 Markdown templates from static/templates to repository root.

Usage: python scripts/template.py

This renders all files matching `static/templates/*.md.j2` and writes the
rendered output to the repository root with the `.j2` suffix removed.
No template variables are provided (empty context) for this initial setup.
"""

import subprocess
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape


def _build_flags_table(ns: dict) -> str:
    """Build flags table markdown from NORTH_STAR.yaml::flag_contracts."""
    try:
        fc = ns.get("flag_contracts", {}) or {}
        all_flags = fc.get("all_flags", []) or []
        lines = []
        lines.append("| Flag | Short | Category |")
        lines.append("| --- | --- | --- |")
        pending_exists = False
        for f in all_flags:
            long = f.get("long") if isinstance(f, dict) else str(f)
            short = f.get("short") if isinstance(f, dict) else None
            short_display = f"`{short}`" if short else ""
            category = f.get("category", "") if isinstance(f, dict) else ""
            is_pending = (
                isinstance(f, dict)
                and f.get("status")
                and "pending" in str(f.get("status"))
            )
            marker = " †" if is_pending else ""
            if is_pending:
                pending_exists = True
            lines.append(f"| `{long}` | {short_display} | {category}{marker} |")
        flags_table = "\n".join(lines)
        if pending_exists:
            flags_table = (
                flags_table + "\n\n*† Contract not yet defined; see pending additions.*"
            )
        return flags_table
    except Exception:
        return ""


def _build_severity_rows(ns: dict) -> list[dict]:
    """Extract severity rows from NORTH_STAR.yaml for template context."""
    severity_rows = []
    try:
        sev = ns.get("severity", {})
        values = sev.get("values", {}) or {}
        gui = sev.get("gui_rendering", {}) or {}

        def render_from_val(v):
            if isinstance(v, dict):
                slot = v.get("slot")
                slot_map = {
                    "error_modal": "error modal",
                    "warning_banner": "warning banner",
                    "log_line": "log line",
                    "suppressed": "suppressed",
                }
                base = slot_map.get(slot, str(slot)) if slot else ""
                if v.get("blocking"):
                    base = f"{base} (blocking)" if base else "(blocking)"
                note = v.get("note")
                if note:
                    base = f"{base} — {note}" if base else note
                return base
            return str(v)

        code_to_render = {}
        for k, v in gui.items():
            kstr = str(k)
            if "-" in kstr:
                a, b = kstr.split("-", 1)
                try:
                    start = int(a)
                    end = int(b)
                except Exception:
                    continue
                for code in range(start, end + 1):
                    code_to_render[code] = render_from_val(v)
            else:
                try:
                    code = int(kstr)
                    code_to_render[code] = render_from_val(v)
                except Exception:
                    continue

        all_codes = set()
        for k in values.keys():
            try:
                all_codes.add(int(k))
            except Exception:
                pass
        for k in code_to_render.keys():
            all_codes.add(int(k))

        for code in sorted(all_codes):
            name = values.get(code, values.get(str(code), f"PRI {code}"))
            rendering = code_to_render.get(code, "")
            severity_rows.append({"code": code, "name": name, "rendering": rendering})
        for r in severity_rows:
            if r.get("code") == 7:
                r["rendering"] = "suppressed by default (see §8.2)"
    except Exception:
        pass
    return severity_rows


def render_templates():
    repo_root = Path(__file__).resolve().parent.parent
    templates_dir = repo_root / "static" / "templates"

    if not templates_dir.exists():
        print(f"Templates directory not found: {templates_dir}", file=sys.stderr)
        return 2

    # Allow templates to include partials stored under static/partials by
    # searching both the templates directory and the static directory.
    env = Environment(
        loader=FileSystemLoader([str(templates_dir), str(repo_root / "static")]),
        autoescape=select_autoescape(enabled_extensions=()),
        keep_trailing_newline=True,
    )

    ns = {}
    north_star_path = repo_root / "static" / "NORTH_STAR.yaml"
    if north_star_path.exists():
        try:
            ns = yaml.safe_load(north_star_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error reading NORTH_STAR.yaml: {e}", file=sys.stderr)

    severity_rows = _build_severity_rows(ns)
    flags_table = _build_flags_table(ns)

    from scop.rfc.base import BaseRFC

    meta_path = repo_root / "static" / "METASCOP.yaml"
    raw = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    model = BaseRFC.model_validate(raw)
    model.north_star = ns  # NORTH_STAR.yaml already loaded above

    # Prepare a mutable dict for rendering and ensure north_star is present
    data = model.model_dump()
    data.setdefault("north_star", ns)

    # Provide a nested TOC structure for advanced partial rendering.
    try:
        from scop.partials.toc import ToCGenerator

        toc_gen = ToCGenerator.from_rfc(model)
        data["toc_nested"] = toc_gen.as_context()
    except Exception:
        data["toc_nested"] = None

    # Render the consumer routing partial (table) and inject it into the
    # "Auto-Translation Rules" section body so subsections (10.1) render after it.
    try:
        routing_tmpl = env.get_template("partials/consumer_routing.md.j2")
        rendered_routing = routing_tmpl.render({**data, "north_star": ns})
    except Exception:
        rendered_routing = None

    if rendered_routing:
        for s in data.get("sections", []):
            if s.get("title", "").strip() == "Auto-Translation Rules":
                s.pop("partial", None)
                s["body"] = rendered_routing
                break

    template = env.get_template("RFC7841.md.j2")
    rendered = template.render(
        {
            **data,
            "severity_rows": severity_rows,
            "flags_table": flags_table,
        }
    )

    out_path = repo_root / "SCOP.md"
    out_path.write_text(rendered, encoding="utf-8")
    written = [out_path]
    print(f"Wrote: {out_path}")

    if not written:
        print("No templates rendered.")
        return 0

    import shutil

    npx = shutil.which("npx")
    if npx is None:
        print("prettier: npx not found, skipping format step", file=sys.stderr)
        return 0

    paths = [str(p) for p in written]
    result = subprocess.run(
        [npx, "--yes", "prettier", "--write", *paths],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"prettier: {result.stderr.strip()}", file=sys.stderr)
        return result.returncode
    return 0


def main():
    """Console entry point for Poetry script: renders templates and returns exit code."""
    return render_templates()


if __name__ == "__main__":
    raise SystemExit(main())
