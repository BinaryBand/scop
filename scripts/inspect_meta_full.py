from pathlib import Path

import yaml

from scop.rfc.base import BaseRFC

p = Path("static/METASCOP.yaml")
raw = yaml.safe_load(p.read_text(encoding="utf-8"))
model = BaseRFC.model_validate(raw)
for s in model.sections:
    if s.title == "Auto-Translation Rules":
        for g in s.subsections:
            if g.title.startswith("Consumer State Model"):
                print(g.body)
                break
        break
