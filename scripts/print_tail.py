from pathlib import Path

p = Path("static/METASCOP.yaml")
lines = p.read_text(encoding="utf-8").splitlines()
for i, line in enumerate(lines[-30:], start=len(lines) - 29):
    print(f"{i:03}: {repr(line)}")
