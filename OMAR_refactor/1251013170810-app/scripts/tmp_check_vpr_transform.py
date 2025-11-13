import json
from pathlib import Path
import sys
sys.path.insert(0, 'OMAR_refactor')
from app.services.transforms import vpr_to_quick_notes
p = Path('OMAR_refactor/examples/vpr_documents_237_20251112T171405Z.json')
raw = json.loads(p.read_text(encoding='utf-8'))
qs = vpr_to_quick_notes(raw)
print('quick items:', len(qs))
if qs:
    first = qs[0]
    print('keys:', sorted(first.keys()))
    for k in ('author','authorProviderType','authorClassification','_author','docId','uid'):
        if k in first:
            print(k, '=>', first[k])
    # check if original raw item had nested text clinicians
    payload = raw.get('payload') if isinstance(raw, dict) else None
    if isinstance(payload, dict):
        data = payload.get('data')
        items = data.get('items') if isinstance(data, dict) else None
    else:
        data = raw.get('data') if isinstance(raw, dict) else None
        items = data.get('items') if isinstance(data, dict) else raw.get('items')
    print('raw first item has nested clinicians in text?', bool(items and isinstance(items[0].get('text'), list) and any(isinstance(b, dict) and b.get('clinicians') for b in items[0].get('text'))))
else:
    print('no quick items')
