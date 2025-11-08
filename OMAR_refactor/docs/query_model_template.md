Query model template (RAG baseline)
===================================

Formerly `app/query/query_models/template_model/README.md`.

Purpose
-------
Provide a minimal retrieval-augmented generation (RAG) implementation using BM25 over patient TIU note chunks with stable excerpt indices.

Included artifacts
------------------
- `provider.py` — Implements:
  - `answer(payload)` — BM25 search, numbered excerpt prompt assembly, LLM call, citation mapping.
  - `rag_results(payload)` — Early list of considered notes with excerpt indices.
- `PROMPT_answer.md` — System prompt.
- `services/` — Thin wrappers re-exporting utilities from the default provider: `sliding_window_chunk`, `remove_boilerplate_phrases`, `build_bm25_index`, `hybrid_search`.

Creating your own model
-----------------------
1. Copy this folder; rename (e.g. `my_team_model`).
2. Edit `provider.py`:
   - Set unique `model_id` and human-friendly `name`.
   - Customize retrieval (add embeddings, scoring heuristics) & prompt composition.
3. Store prompts in `.md` files; load them in code.
4. Add tests under `OMAR_refactor/tests/`.

Contract (payloads)
-------------------
Input to `/api/query/ask`:
```json
{
  "query": "Question text...",   
  "model_id": "your_model_id",
  "patient": { "DFN": "..." }
}
```
Output:
```json
{
  "answer": "...",
  "citations": [ { "excerpt": 1, "note_id": "...", "title": "...", "date": "...", "preview": "..." } ],
  "model_id": "your_model_id"
}
```

Simple RAG flow
---------------
1. Chunk notes (~1600 chars, 800-char step); strip boilerplate.
2. BM25 index (unigram + bigram tokens).
3. Score chunks; select top 12 with diversity cap (≤3 per note).
4. Assemble prompt with numbered `(Excerpt N)` headers (title + date).
5. Call LLM; UI renders answer + citations.

Extension tips
--------------
- Embeddings: integrate vector store; perform hybrid search before fusion.
- Structured data: fetch labs / meds; append concise tables pre-excerpts.
- Long-context: add window expansion around top chunks for surrounding narrative.
- Hallucination mitigation: shorten prompt, enforce excerpt citation markers, post-filter unsupported sentences.

Testing
-------
Mock retrieval functions to return deterministic chunk list; assert citation mapping and excerpt numbering. Provide sample patient note fixture.

Best practices
--------------
- Keep prompt concise; avoid redundant demographic info.
- Ensure excerpt texts are clean (remove disclaimers boilerplate).
- Limit answer length; encourage evidence-backed phrasing.

See also
--------
- `docs/query_subsystem_overview.md` — Endpoint + model discovery
- `docs/backend_app_structure.md` — Overall architecture
