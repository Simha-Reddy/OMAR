Template Hey OMAR Query Model
=============================

This template's full documentation has moved to `docs/query_model_template.md`.

Quick start:
1. Copy this folder, rename it (`my_team_model`).
2. Edit `provider.py`: set `model_id`, `name`, customize `answer()` / `rag_results()`.
3. Add prompts (`PROMPT_answer.md`, etc.) and tests under `OMAR_refactor/tests/`.

Contract summary (see full docs for details):
Input payload:
```json
{ "query": "Question text...", "model_id": "your_model_id", "patient": { "DFN": "..." } }
```
Output payload:
```json
{ "answer": "...", "citations": [ { "excerpt": 1, "note_id": "..." } ], "model_id": "your_model_id" }
```

For RAG flow, scoring heuristics, and extension tips, read `docs/query_model_template.md`.

Rationale: Centralizing technical READMEs under `docs/` keeps architecture docs discoverable and consistent. This stub remains so copied models include a pointer.

