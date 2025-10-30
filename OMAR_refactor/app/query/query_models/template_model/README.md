Template Hey OMAR Query Model

How to create your own model:
1) Copy this folder and rename it (e.g., `my_team_model`).
2) Open `provider.py` and set:
  - `model_id` (machine-friendly, unique)
   - `name` (human-friendly)
   - Implement the `answer(payload)` method.
3) Put any prompts in `.md` files in this folder, then read them in your code.
4) Optional: add small tests under `OMAR_refactor/tests/` that import your model and check the contract.

Contract:
- Input JSON to `/api/query/ask`:
  {
    "prompt": "Question text...",
    "model_id": "your_model_id",
    "patient": { ... optional context ... }
  }
- Output JSON:
  {
    "answer": "...",
    "citations": [ { "title": "...", "date": "...", "note_id": "..." } ],
    "model_id": "your_model_id"
  }

Keep responses short and add citations when you use chart data.
