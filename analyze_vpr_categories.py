import json

with open('VPRpatientexample.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data.get('payload', {}).get('data', {}).get('items', [])
category_names = set()
display_groups = set()
document_classes = set()

for item in items:
    if 'categoryName' in item:
        category_names.add(item['categoryName'])
    if 'displayGroup' in item:
        display_groups.add(item['displayGroup'])
    if 'documentClass' in item:
        document_classes.add(item['documentClass'])

with open('VPR_analysis.txt', 'w', encoding='utf-8') as out:
    out.write('Unique categoryName values:\n')
    for name in sorted(category_names):
        out.write(f'- {name}\n')
    out.write('\nUnique displayGroup values:\n')
    for group in sorted(display_groups):
        out.write(f'- {group}\n')
    out.write('\nUnique documentClass values:\n')
    for doc_class in sorted(document_classes):
        out.write(f'- {doc_class}\n')
