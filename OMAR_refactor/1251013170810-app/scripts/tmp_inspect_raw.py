import json
from pathlib import Path
import sys
sys.path.insert(0, 'OMAR_refactor')
path = Path('OMAR_refactor/examples/vpr_documents_237_20251112T171405Z.json')
raw = json.loads(path.read_text(encoding='utf-8'))
items = None
if isinstance(raw, dict):
    data = raw.get('payload') if isinstance(raw.get('payload'), dict) else raw.get('data')
    if isinstance(data, dict) and isinstance(data.get('items'), list):
        items = data['items']
    elif isinstance(raw.get('items'), list):
        items = raw['items']
if not items:
    raise SystemExit('No items found')
first = items[0]
print('top-level keys:', sorted(first.keys()))
print('top-level clinicians type:', type(first.get('clinicians')).__name__)
print('top-level clinicians value:', first.get('clinicians'))
text = first.get('text')
if isinstance(text, list) and text:
    print('first text entry keys:', text[0].keys())
    print('first text entry clinicians type:', type(text[0].get('clinicians')).__name__)
    print('first text entry clinicians value:', text[0].get('clinicians'))
