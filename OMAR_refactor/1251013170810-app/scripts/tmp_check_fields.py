import json
from pathlib import Path
import sys
sys.path.insert(0, 'OMAR_refactor')
from app.services.transforms import vpr_to_quick_notes
p = Path('OMAR_refactor/examples/vpr_documents_237_20251112T171405Z.json')
raw = json.loads(p.read_text(encoding='utf-8'))
qs = vpr_to_quick_notes(raw)
missing_author = sum(1 for item in qs if not item.get('author'))
missing_type = sum(1 for item in qs if not item.get('authorProviderType'))
missing_class = sum(1 for item in qs if not item.get('authorClassification'))
print('total:', len(qs))
print('missing author:', missing_author)
print('missing provider type:', missing_type)
print('missing classification:', missing_class)
for item in qs[:5]:
    subset = {k: item.get(k) for k in ('title','author','authorProviderType','authorClassification')}
    print(subset)
