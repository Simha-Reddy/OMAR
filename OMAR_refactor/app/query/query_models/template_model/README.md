Template Hey OMAR Query Model

This folder is a minimal, copyable starting point for creating your own Hey OMAR provider.
It performs a simple RAG (retrieval-augmented generation) over the current patient's TIU notes
using a BM25 keyword index and a sliding-window chunker. It reuses helper functions from the
default provider to avoid duplicating code.

What’s included

- `provider.py` — a simple provider that implements:
  - `answer(payload)` — runs a basic BM25-only hybrid search (no embeddings by default),
    assembles a prompt with numbered excerpts, calls the configured LLM, and returns citations.
  - `rag_results(payload)` — returns an early “Notes considered” list with stable excerpt indices.
- `PROMPT_answer.md` — short system prompt the provider uses.
- `services/` — thin wrappers that re-export utilities from the default model:
  - `sliding_window_chunk`, `remove_boilerplate_phrases`, `build_bm25_index`, `hybrid_search`.

How to create your own model

1) Copy this folder and rename it (e.g., `my_team_model`).
2) Edit `provider.py` and set:
   - `model_id` (machine-friendly, unique)
   - `name` (human-friendly)
   - Customize `answer()` and `rag_results()` as needed.
3) Put any prompts in `.md` files and read them in your code (example: `PROMPT_answer.md`).
4) Optional: add tests under `OMAR_refactor/tests/` for your provider.

Contract (payloads)

Input to `/api/query/ask`:

```
{
  "query": "Question text...",   // preferred; "prompt" is also accepted
  "model_id": "your_model_id",
  "patient": { "DFN": "..." }  // optional; DFN is usually injected from session
}
```

Model output:

```
{
  "answer": "...",                 // HTML or markdown-compatible text
  "citations": [                   // list used by the UI to render (Excerpt N) links
    { "excerpt": 1, "note_id": "...", "title": "...", "date": "...", "preview": "..." }
  ],
  "model_id": "your_model_id"
}
```

Simple RAG used here (what this template does)

1. Build chunks: fetch the patient’s DocumentSearchIndex (full note texts) and create
   overlapping chunks (~1600 chars with 800-char step). Clean common boilerplate.
2. Index: build a BM25 index over chunks (unigram + bigram tokens).
3. Retrieve: score chunks against the query and pick the top 12, with a diversity cap of 3 per note.
4. Prompt: assemble a prompt with numbered “(Excerpt N)” headers that include the note title and date.
5. Answer: call the configured LLM; the UI post-processes citations and provides a note viewer.

Tips

- Want embeddings or custom scoring? Replace the thin wrappers in `services/` with your own code,
  or import the default provider’s embedding logic.
- Need to add structured data (labs/vitals/meds) into the prompt? Call server services from `provider.py`
  and append concise tables before the excerpts.
- Keep answers short and ensure facts are supported by excerpts.

