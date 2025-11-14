Query subsystem overview (Hey OMAR)
===================================

Last updated: 2025-11-07

Migrated from `app/query/README.md`.

Endpoint
--------
`POST /api/query/ask`
Input JSON:
```json
{ "prompt": "...", "model_id": "default", "patient": { /* optional */ } }
```
Output JSON:
```json
{ "answer": "...", "citations": [ ... ], "model_id": "..." }
```

Models live under `app/query/query_models/`:
- `default/` — Baseline provider
- `template_model/` — Copy-ready starting point (see `docs/query_model_template.md`)

Contracts
---------
Models implement interface in `contracts.py` and are auto-discovered by `registry.py` (`QueryModelRegistry`). Each provider returns an `answer` plus structured citation list (excerpt indices, note metadata) consumed by the UI for linking.

Implementation notes
--------------------
Create a provider in `provider.py` exporting `model` implementing `QueryModel`.
Discovery via registry enumerating subdirectories.
Unified endpoint selects `model_id` (defaults when omitted).

See also
--------
- `docs/backend_app_structure.md` — Overall server architecture
- `docs/query_model_template.md` — Guidance for building new models
