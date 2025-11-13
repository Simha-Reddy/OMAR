# Static JavaScript Libraries

This directory contains locally cached versions of external JavaScript libraries to avoid dependencies on external CDNs.

## Available Libraries

### Tabulator (Table Library)
- **tabulator.min.css** - Tabulator CSS v6.3.0 (latest)
- **tabulator.min.js** - Tabulator JavaScript v6.3.0 (latest)
- **tabulator-5.5.0.min.css** - Tabulator CSS v5.5.0 (for compatibility)
- **tabulator-5.5.0.min.js** - Tabulator JavaScript v5.5.0 (for compatibility)

### Marked (Markdown Parser)
- **marked.min.js** - Marked JavaScript for parsing Markdown

## Usage in HTML

```html
<!-- CSS -->
<link href="/static/lib/tabulator.min.css" rel="stylesheet">

<!-- JavaScript -->
<script src="/static/lib/marked.min.js"></script>
<script src="/static/lib/tabulator.min.js"></script>
```

## Original Sources

- Tabulator: https://unpkg.com/tabulator-tables/
- Marked: https://cdn.jsdelivr.net/npm/marked/

## Updates

To update these libraries:
1. Download the latest versions from the CDNs
2. Replace the files in this directory
3. Update version references in the code if needed
