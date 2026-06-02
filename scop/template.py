

"""Render Jinja2 Markdown templates from static/templates to repository root.

Usage: python scripts/template.py

This renders all files matching `static/templates/*.md.j2` and writes the
rendered output to the repository root with the `.j2` suffix removed.
No template variables are provided (empty context) for this initial setup.
"""

from pathlib import Path
import toml
import sys

from jinja2 import Environment, FileSystemLoader, select_autoescape
"""Render Jinja2 Markdown templates from static/templates to repository root.

Usage: python scripts/template.py

This renders all files matching `static/templates/*.md.j2` and writes the
rendered output to the repository root with the `.j2` suffix removed.
No template variables are provided (empty context) for this initial setup.
"""

from pathlib import Path
import toml
import sys
import yaml

from jinja2 import Environment, FileSystemLoader, select_autoescape


DEFAULT_VERSION = "0.1.0"



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

    # Default version; may be overridden by NORTH_STAR.yaml.spec_version
    version = DEFAULT_VERSION

    # Load NORTH_STAR.yaml to generate stable severity rows for the partial.
    severity_rows = []
    ns = {}
    north_star_path = repo_root / "static" / "NORTH_STAR.yaml"
    if north_star_path.exists():
        try:
            ns = yaml.safe_load(north_star_path.read_text(encoding='utf-8'))
            # Use spec_version from NORTH_STAR.yaml if present
            try:
                version = ns.get("spec_version", DEFAULT_VERSION)
            except Exception:
                version = DEFAULT_VERSION
            sev = ns.get("severity", {})
            values = sev.get("values", {}) or {}
            gui = sev.get("gui_rendering", {}) or {}

            # helper to produce human text from a gui_rendering entry
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
                        # non-numeric key (ignore)
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
            # Override DEBUG rendering to reference the flag contract section
            for r in severity_rows:
                if r.get("code") == 7:
                    r["rendering"] = "suppressed by default (see §8.2)"
        except Exception as e:
            print(f"Error reading NORTH_STAR.yaml: {e}", file=sys.stderr)

    # Build flags table markdown from NORTH_STAR.yaml::flag_contracts
    flags_table = ""
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
            short_display = f"`{short}`" if short else "`-`"
            category = f.get("category", "") if isinstance(f, dict) else ""
            is_pending = isinstance(f, dict) and f.get("status") and "pending" in str(f.get("status"))
            marker = " †" if is_pending else ""
            if is_pending:
                pending_exists = True
            lines.append(f"| `{long}` | {short_display} | {category}{marker} |")
        flags_table = "\n".join(lines)
        if pending_exists:
            flags_table = flags_table + "\n\n*† Contract not yet defined; see pending additions.*"
    except Exception:
        flags_table = ""

    pattern = "*.j2"
    written = []

    for tpl_path in templates_dir.glob(pattern):
        # Only process files that look like markdown templates (*.md.j2)
        if not tpl_path.name.endswith('.j2'):
            continue

        out_name = tpl_path.name[:-3]  # strip .j2
        out_path = repo_root / out_name

        template = env.get_template(tpl_path.name)
        rendered = template.render({"version": version, "severity_rows": severity_rows, "north_star": ns, "flags_table": flags_table})

        out_path.write_text(rendered, encoding='utf-8')
        written.append(out_path)
        print(f"Wrote: {out_path}")

    if not written:
        print("No templates rendered.")
    return 0


def main():
    """Console entry point for Poetry script: renders templates and returns exit code."""
    return render_templates()


if __name__ == "__main__":
    raise SystemExit(main())