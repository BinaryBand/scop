

"""Render Jinja2 Markdown templates from static/templates to repository root.

Usage: python scripts/template.py

This renders all files matching `static/templates/*.md.j2` and writes the
rendered output to the repository root with the `.j2` suffix removed.
No template variables are provided (empty context) for this initial setup.
"""

from pathlib import Path
import sys

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except Exception as e:
    print("Jinja2 is required. Install with: pip install Jinja2", file=sys.stderr)
    raise


def render_templates():
    repo_root = Path(__file__).resolve().parent.parent
    templates_dir = repo_root / "static" / "templates"

    if not templates_dir.exists():
        print(f"Templates directory not found: {templates_dir}", file=sys.stderr)
        return 2

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(enabled_extensions=()),
        keep_trailing_newline=True,
    )

    pattern = "*.j2"
    written = []

    for tpl_path in templates_dir.glob(pattern):
        # Only process files that look like markdown templates (*.md.j2)
        if not tpl_path.name.endswith('.j2'):
            continue

        out_name = tpl_path.name[:-3]  # strip .j2
        out_path = repo_root / out_name

        template = env.get_template(tpl_path.name)
        rendered = template.render({})

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