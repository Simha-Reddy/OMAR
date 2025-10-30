Hey OMAR Query backend

- POST /api/query/ask
  Input JSON: { "prompt": "...", "model_id": "default" (or your model id), "patient": {optional} }
  Output JSON: { "answer": "...", "citations": [ ... ], "model_id": "..." }

Query models live under `app/query/query_models/`.
- `default/` contains the current Hey OMAR baseline.
- `template_model/` is a copy-ready starting point with docs.

Models implement the contract in `contracts.py` and are auto-discovered by `registry.py`.
