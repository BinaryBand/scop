import yaml
from scop.rfc.base import BaseRFC
from pathlib import Path
p = Path('static/METASCOP.yaml')
raw = yaml.safe_load(p.read_text(encoding='utf-8'))
model = BaseRFC.model_validate(raw)
for s in model.sections:
    if s.title == 'Auto-Translation Rules':
        print('Found Auto-Translation Rules')
        for g in s.subsections:
            print(' Subsection:', g.title)
            print(' Body head:')
            print('\n'.join(g.body.splitlines()[:40]))
            print('---END BODY---')
            break
        break
else:
    print('Auto-Translation Rules section not found')
