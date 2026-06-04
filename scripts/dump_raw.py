from pathlib import Path

import yaml

p = Path("static/METASCOP.yaml")
raw = yaml.safe_load(p.read_text(encoding="utf-8"))
for s in raw.get("sections", []):
    if s.get("title") == "Auto-Translation Rules":
        for g in s.get("subsections", []):
            if g.get("title", "").startswith("Consumer State Model"):
                body = g.get("body", "")
                print("RAW BODY LEN:", len(body))
                print(body[-1500:])
                break
        break
