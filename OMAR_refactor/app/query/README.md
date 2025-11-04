Hey OMAR Query backend

- POST /api/query/ask
  Input JSON: { "prompt": "...", "model_id": "default" (or your model id), "patient": {optional} }
  Output JSON: { "answer": "...", "citations": [ ... ], "model_id": "..." }

Query models live under `app/query/query_models/`.
- `default/` contains the current Hey OMAR baseline.
- `template_model/` is a copy-ready starting point with docs.

Models implement the contract in `contracts.py` and are auto-discovered by `registry.py`.

Implementation notes:
- Implement a `provider.py` (or `query_model.py`) that exports `model` implementing `QueryModel`.
- Discovery is handled by `QueryModelRegistry` (aliased as `ModelRegistry` for back-compat).
- The unified endpoint `/api/query/ask` will route to the selected `model_id` (default when omitted).
