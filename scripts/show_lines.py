from pathlib import Path
p=Path('static/METASCOP.yaml')
text=p.read_text(encoding='utf-8')
lines=text.splitlines()
for i,line in enumerate(lines, start=1):
    if i>=200 and i<=320:
        print(f"{i:03}: {repr(line)}")
