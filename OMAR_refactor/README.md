# OMAR

OMAR is an AI-connected clinical assistant for VA clinicians, intended to run alongside a primary EHR. It is a work-in-progress focused on reimagining the clinician's workspace, as well as integrating AI in a natural and carefully limited way. It includes ambient scribing of notes, tracking of tasks and orders, patient instruction creation, and a powerful natural language query system of the patient's chart.

While functional now, OMAR is a framework, not a final product. It's intended to be modular and to grow over time. New query models can be dropped in and tested. New tabs that find new and effective ways of presenting information, with or without an AI connection, are encouraged. Please consider contributing.

> OMAR IS NOT INTENDED FOR CLINICAL USE AT THIS TIME (OCTOBER 2025). FOR TESTING ONLY.

---

## Quick plain-language overview (for clinicians)

What OMAR does for you:

- Ambient scribe: Listen during a visit, transcribe audio, and draft a structured note from a template you choose.
- Hey OMAR: Ask natural-language questions about the chart ("When was the last A1c?") and get concise answers with clickable citations that open the original note excerpt.
- Snapshot: View problems, medications, vitals, and labs at a glance.
- Documents: Quickly keyword search all documents for a patient.
- Dot-phrases (planned; not yet implemented): Insert short commands inside your note (e.g., `.vitals/180`, `.meds/active`) to expand current structured data.
- Patient instructions: Generate clear, editable instructions you can export as a PDF.

How to use it (typical flow):

1. Launch OMAR in your browser (currently requires starting a separate program on your local computer, but short-term goal is to be available via secure login to a site on the VA network).
2. Sign in with your VistA/CPRS credentials (when configured to use VistA).
3. The program will sync to the last patient you reviewed in CPRS, or you can select a patient from the search bar.
4. Use the Note controls to start/stop transcription and create a draft note.
5. Use the Hey OMAR box to ask questions or get a patient summary; click any (Excerpt N) citation to open the source note.
6. Review and search documents and other data on other tabs.

Important: OMAR surfaces information from patient charts and drafts notes for clinician review — it does not order tests, prescribe, autonomously make clinical decisions, or provide clinical recommendations.

---

## Design philosophy

- Clinician-first, low friction: optimize for fewer clicks and faster pivots between common tasks.
- Transparency builds trust: every fact should link back to a source excerpt with date/title.
- Compact and relevant: keep answers short, prioritize recent information and assessment/plan material.
- Few modes, fast pivots: Reorder and save tab configurations, return to where you left off without losing context.
- Assist, don’t decide: no autonomous ordering, no clinical recommendations; clinicians stay in control.
- Privacy by default: minimize PHI movement, keep data local when possible, and make retention explicit.
- Modular by design: query models and UI tabs are plug-in style so OMAR can grow over time.

---

## Scope & safety boundaries

- No clinical recommendations. OMAR assists with search, summarization, and drafting only.
- Answers include citations; always verify against source notes before acting.
- Does not replace clinical judgment. Information may be incomplete or out of date.
- PHI handling: keep data on the server in-memory and temporary; configure retention; avoid PHI in logs; browser responses use no-store where appropriate. Archiving of notes and transcripts on the server can be explicitly allowed, with routine time-limits on retention.
- External services: only site-approved endpoints within the VA network (e.g., enterprise LLM/speech); require HTTPS.
- Clinical use beyond testing requires institutional approval and validation.

---

## Technical overview

This section explains where key code lives, how patient data is obtained, and how the system assembles answers.

Project layout (important folders)

- `OMAR_refactor/` — active application code used for development and deployment.
- `OMAR_refactor/app/` — Flask application package (blueprints, services, query model providers).
- `OMAR_refactor/static/` — front-end JavaScript, CSS, images. Look under `static/js/workspace/modules/` for tab modules like `heyomar.js` and `snapshot.js`.
- `OMAR_refactor/templates/` — HTML templates and prompt templates used by the backend.
- `OMAR_refactor/app/query/query_models/` — Hey OMAR providers live here. See `default/` for the built-in model and `template_model/` for a copyable starting point (with its own README).
- `OMAR_refactor/app/gateways/` - Connection to VistA via vista-api-x
- `OMAR_refactor/static/js/note.js` — browser-side audio capture (NoteRecorder) used by the Note (scribe) tab.
- `requirements.txt` — Python dependencies for the environment used to run OMAR.

How patient data is obtained

- Current gateway: vista-api-x ("Vista API X"). OMAR calls this API as the single entry point for patient data instead of talking to VistA directly.
- vista-api-x brokers VistA RPCs OMAR invokes its endpoints to fetch the VPR bundle ("GET PATIENT DATA JSON") and TIU document content.
- The returned VPR JSON (encounters, meds, labs, document refs) is consumed directly by OMAR_refactor. Lightweight mapping to UI-friendly shapes is handled in `OMAR_refactor/app/services/transforms.py` (e.g., demographics, medications, labs, vitals, notes) for Snapshot/Explore/Hey OMAR.
- TIU documents (notes) are retrieved via vista-api-x and indexed for search. Each chunk keeps metadata such as note id, local title, nationalTitle (if available), author, timestamp, and stable excerpt index.

Privacy note about patient data

- By default, OMAR keeps patient data local to the server instance started for a session, and remains in-memory only while session is running. Configure retention and archival policies on the server to meet local privacy requirements.

---

## Data flow (OMAR_refactor)

High-level flow from data sources to the UI:

```
[Browser UI]
  |  (Snapshot, Documents, Hey OMAR, Note, etc.)
  v
[Flask API]
  |-- fetch patient bundle / documents --> [vista-api-x]
  |                                        (CPRS ACCESS/VERIFY handled server-side)
  v
[VPR GET PATIENT DATA JSON (patient bundle)]
  |-- quick mappings --> app/services/transforms.py
  |                     (demographics, meds, labs, vitals, notes)
  |                         -> Snapshot / Explore
  |
  |-- indexing (per patient) --> DocumentSearchIndex
                    (note text + metadata incl. nationalTitle, date, excerpt index)
                       -> used by Hey OMAR retrieval

Hey OMAR (Query Provider)
  |-- retrieves top excerpts (max 12, <=3 per note)
  |-- assembles clinical preface + context
  |-- calls LLM
  v
[Concise answer + clickable citations (Excerpt N)]
```

Notes:
- vista-api-x is the single gateway OMAR_refactor uses for VistA data.
- VPR GET PATIENT DATA JSON is consumed directly.
- Transforms in `app/services/transforms.py` produce lightweight, UI-friendly shapes.
- The per-patient DocumentSearchIndex powers RAG for Hey OMAR.


---

## How the Note Scribe works (high-level)

- Audio capture (front-end): The user must get explicit consent from anyone being recorded. `OMAR_refactor/static/js/note.js` (NoteRecorder) captures microphone input in the browser using MediaRecorder/WebAudio, chunks audio (WAV), and streams it to the server. 
- Transcription: audio segments are sent to the configured speech-to-text provider (Azure Speech or another configured provider). Transcription results are returned in near-real-time.
- Assembly: Transcripts are combined with anything currently in the editable Draft Note box, and the user selected prompt. These are sent to the LLM and a draft note is returned. If the default prompts are not sufficient, the user can add a custom prompt on the Settings page.
- Draft lifecycle: drafts are saved in the session workspace and may be copied. They are not automatically signed or sent to the EHR — that remains a clinician action.

---

## Hey OMAR: structure and multi-model plan

What Hey OMAR is

- Hey OMAR is the conversational query interface (the "assistant") that takes clinician questions, runs retrieval over indexed chart text, and asks an LLM to synthesize answers which include citations back to source excerpts.

Where the code lives

- Front-end: `static/js/workspace/modules/heyomar.js` (UI logic, rendering early RAG lists, clickable citations, and modal note viewers).
- Backend endpoints: `app/query/blueprints/query_api.py` exposes `/api/query/ask`, `/api/query/rag_results`, and `/api/query/reset`.
- Model providers: `OMAR_refactor/app/query/query_models/<provider>/provider.py` — pluggable providers implement the same interface.

Multi-model plan (how multiple models are supported)

- OMAR uses a provider abstraction for models. Each provider implements a set of functions (e.g., `answer(payload)` and `rag_results(payload)`) and is registered in configuration.
- The front-end sends requests to `/api/query/ask` with a `mode` or `provider` override. The backend looks up the requested provider and delegates the work.
- This design allows swapping between on-premise models, managed cloud models, or experimental local models without changing the front-end UI.

---

## Default model pipeline (current)

The default provider performs an in-model Retrieval-Augmented-Generation (RAG) pipeline with these highlights:

1. Document processing
- Remove boilerplate and duplicates: common headers/footers, signature blocks, page banners, and date/signed lines are stripped; empty and duplicate chunks are dropped. (see `OMAR_refactor/app/query/query_models/default/services/rag.py`: `remove_boilerplate_phrases`, `clean_chunks_remove_duplicates_and_boilerplate`).
- Page tagging: simple page detection assigns page numbers and offsets to chunks when markers are present. (see `default/services/rag.py`: `tag_chunks_with_page`).
- Sliding-window chunking: TIU notes are split with a large window and overlap; stable excerpt indices are assigned per note in first-appearance order. (see `default/services/rag.py`: `sliding_window_chunk`; chunks built in `default/provider.py`: `_build_chunks_from_document_index`).
- Metadata: each chunk retains note id, local title, nationalTitle (if available, these can help distinguish categories of notes like nursing or social work), date/time, and the excerpt index. (set in `default/provider.py`: `_build_chunks_from_document_index`).

2. Retrieval
 - A hybrid search combines semantic embeddings (Azure OpenAI/text-embedding-3-large or similar) and a BM25 keyword index. (see `default/services/rag.py`: `build_bm25_index`, `hybrid_search`; embeddings via `app/ai_tools/embeddings`).
 - Hybrid scores are fused, and additional boosts are applied: recency, section-type (e.g., Assessment/Plan), title overlap, and a tag boost computed from the nationalTitle when available. (nationalTitle tag boost is added at search time via per-chunk `tag_boost` in `default/provider.py`: `answer` using `default/services/title_tagging.py`: `score_for_title`; consumed in `rag.py`: `hybrid_search`).
 - Where the nationalTitle boost applies: the nationalTitle-based boost is injected at search time as a per-chunk `tag_boost` and fused into the hybrid score. After retrieval, an optional light re-ranker may sort by title tags again; this post-step currently uses the local title, not the nationalTitle. (see `default/provider.py`: `answer` post-retrieval sort by `score_for_title`).
- The retriever returns up to 12 candidate chunks per query with a per-note cap of 3 chunks to maintain diversity.

3. Context assembly
- The top excerpts are assembled into a prompt with optional structured sections (vitals, labs, meds) and a small number of recent Q/A exchanges for context.

4. Model answer
- The provider calls the configured LLM with the assembled context and an instruction template that asks for a concise answer with inline citations in the form `(Excerpt N)`.
- The response is post-processed for markdown, citation anchoring, and presentation.

5. Early RAG list
- The backend can return an early "Notes considered" list (via `/api/query/rag_results`) so the front-end can show the clinician which notes were used, before the final answer arrives.

---

## Developer section — how to add your own model provider

Contract (what your provider must do)

- Implement a provider module with at least two functions:
  - `answer(payload)` — accept the query payload and return an object with `{ answer_html, sources, rag_debug }` where `sources` map excerpt indices to metadata used by the UI.
  - `rag_results(payload)` — (optional) return an early list of notes/excerpts considered with stable excerpt numbering.

Recommended location and pattern

- Create a folder `OMAR_refactor/app/query/query_models/<your_provider>/` and add `provider.py`. Look at `OMAR_refactor/app/query/query_models/default/provider.py` as a reference for how to:
  - Use the DocumentSearchIndex
  - Build prompts from templates in `templates/` (e.g., `health_summary_prompt.txt`)
  - Respect chat history per patient

Configuration

- Add your provider name to the app configuration (e.g., `DEFAULT_QUERY_PROVIDER` or a list of available providers). The API will route requests to your provider when requested.

Testing

- Add unit tests under `tests/` that exercise `answer()` and `rag_results()` with mocked DocumentSearchIndex and model calls.

---

## Developer section — how to add a new workspace tab (UI module)

1. Front-end module
- Add a JS file under `static/js/workspace/modules/yourtab.js` that exports an initialization function the workspace can call to create the tab UI.
- Use the existing modules as an example (see `heyomar.js`, `snapshot.js`). Each module typically:
  - Renders a small DOM fragment into the workspace
  - Uses `static/js/api.js` to talk to backend endpoints
  - Registers click handlers and manages UI state

2. Register in the workspace shell (HTML/JS)
- Map your tab’s display name to its file in `static/js/workspace.js` under `moduleConfig`, for example:
  - `moduleConfig['My Tab'] = 'my_tab.js'`
- Add your tab to the default layout in `static/js/workspace.js` by inserting its name into the `initialTabs` array. The first five go in the left pane; the rest go in the right pane. Users can later reorder and the layout persists per user in localStorage.
- The workspace bootstraps modules by looking for `window.WorkspaceModules['My Tab']` after it loads `/static/js/workspace/modules/my_tab.js`. Your module should register itself like:
  - `window.WorkspaceModules['My Tab'] = { render: async (container, opts) => { /* ... */ }, refresh: async () => {/* optional */} }`.
- If your tab also uses a server-side HTML partial, place it under `templates/tabs/` and fetch or include it from your module’s render.

3. Backend endpoints you can use (and how to call them)
- Use the built-in patient-scoped APIs via `static/js/api.js` (DFN is handled for you):
  - Quick transforms: `GET /api/patient/{DFN}/quick/{domain}` → `Api.quick('demographics')`, `Api.quick('meds', { status:'active' })`
  - Raw VPR domains: `GET /api/patient/{DFN}/vpr/{domain}` → `Api.vpr('labs', { range:'1Y' })`
  - List helpers: `GET /api/patient/{DFN}/list/{domain}` → `Api.list('documents', { limit: 50 })`
  - Documents: `GET /api/patient/{DFN}/documents/search?query=...`, `POST /api/patient/{DFN}/documents/text-batch` → `Api.documentsSearch({...})`, `Api.documentsTextBatch(ids)`
  - Query/RAG: `POST /api/query/ask`, `POST /api/query/rag_results`, `POST /api/query/reset` → `Api.ask(q, { model_id })`, `Api.ragResults(q, { model_id })`, `Api.resetQueryHistory({ model_id })`
- For custom functionality, add a Flask blueprint under `app/blueprints/yourtab.py` with routes such as:
  - Patient-scoped: `GET /api/patient/<dfn>/yourtab/stats`, `POST /api/patient/<dfn>/yourtab/action`
  - App-scoped: `GET /api/yourtab/options`, `POST /api/yourtab/compute`
  - Prefer JSON responses; include CSRF for mutating requests. The front end’s `csrf_fetch.js` automatically attaches the CSRF header when you call `Api.csrfFetch()` or `Api.*` helpers.
  - Keep PHI server-side; return only what the UI needs and avoid logging PHI.

---

## How to contribute

- Fork, branch, and submit a pull request; include tests for new behavior.
- Keep PHI and API keys out of code, issues, and logs. Use synthetic or scrubbed test data.

---
## License

MIT (for research and internal deployment). Do not deploy clinically without institutional approval and validation.

