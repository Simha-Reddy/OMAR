# Front-end Refactor Plan (Legacy OMAR parity → VPR-first)

This plan maps the legacy OMAR front-end behaviors and endpoints to the OMAR_refactor VPR-first backend, and lays out a phased approach to reach UI parity while simplifying client logic.

## Scope and assumptions

- Product reference: legacy `OMAR/` front-end look/behavior. Source assets have been copied into `OMAR_refactor/static` and `OMAR_refactor/templates` for adaptation.
- Data source: vista-api-x (VPR) only. SMART/FHIR and CPRS RPC integrations are out of scope for this pass.
- Security and sessions: CSRF double-submit cookie is enforced. Session stores `station`/`duz`; DFN is carried in the request URL path rather than session.

## Tiny contracts to guide refactor

- Patient scoping: All data calls are under `/api/patient/<DFN>/...`. Front-end must hold the current DFN (e.g., in `sessionStorage`), not the server session.
- Station/DUZ: Provide once via `?station=500&duz=983` on any early call; values persist in the server session for subsequent calls.
- Shapes:
  - Quick endpoints: `/api/patient/<dfn>/quick/{documents|labs|meds|vitals|radiology|notes|problems|allergies|encounters|procedures|demographics}` return UI-ready shapes.
  - List envelopes: `/api/patient/<dfn>/list/{documents|labs|meds|vitals|radiology}` → `{ items, next, total }` with `limit/next` pagination.
  - Flags: `includeText=1`, `includeEncounter=1`, `includeRaw=1` enrich quick results; use only when needed.
- Dates and ranges: Pass `start/stop` as ISO or yyyymmdd[HHMM[SS]]; or use `last=14d|2w|6m|1y`. Back-end converts to FileMan.
- CSRF fetch: Keep the double-submit header (`X-CSRF-Token` = cookie `csrf_token`) for non-GETs.

## Legacy → Refactor endpoint mapping

Core patient/session
- GET `/get_patient` → GET `/api/patient/<dfn>/quick/demographics` (client must already know DFN).
- POST `/select_patient` → No server-side session DFN. New flow: client sets DFN (URL or storage), then calls demographics to validate and hydrate UI. Optional helper: add a light front-end-only shim function that returns demographics and sets local DFN.
- POST `/clear_session` → Remove. Not required for patient switching; client clears its own local state. Session holds `station/duz` only.
- POST `/vista_sensitive_check` → Not available. Defer or replace with a no-op UI notice for now.
- POST `/vista_patient_demographics` → GET `/api/patient/<dfn>/quick/demographics`.
- POST `/vista_rpc` (CPRS sync) → Not available in refactor. De-scope CPRS-dependent flows.

Data domains (replace unscoped calls with DFN-scoped APIs)
- Any `/quick/*` without DFN → `/api/patient/<dfn>/quick/*`
  - Examples: `quick/vitals`, `quick/labs`, `quick/meds`, `quick/notes`, `quick/documents`, `quick/radiology`, `quick/procedures`, `quick/encounters`, `quick/problems`, `quick/allergies`, `quick/demographics`.
  - Documents/Notes: Use `/quick/documents` with filters instead of legacy note/document splits.
- Any `/list/*` → `/api/patient/<dfn>/list/*` with `limit/next` and optional filters.
- Raw VPR passthrough → `/api/patient/<dfn>/vpr/<domain>`; single item via `/api/patient/<dfn>/vpr/<domain>/item?uid=...`.

Documents and text
- Batch text endpoints like `/documents_text_batch` → Prefer `/quick/documents?includeText=1` and cache client-side when needed.

AI/Explore
- POST `/explore/notes_qa` → POST `/api/query/ask` with body `{ prompt, model_id: "default", patient: { DFN: "<dfn>" } }`.

Scribe (note tab)
- Legacy `/scribe/*` commands map (where available) to `/api/scribe/*`:
  - Create session: `POST /api/scribe/session { patient_id: <dfn> }` → `{ session_id }`
  - Stream chunk: `POST /api/scribe/stream?session_id=...&seq=N` (binary audio)
  - Status: `GET /api/scribe/status?session_id=...`
  - Stop: `POST /api/scribe/stop?session_id=...`
- Not available: `stop_recording`, `start_recording`, `clear_live_transcript`, `live_transcript`, `create_note`, `chat_feedback`. For parity, either disable advanced scribe UX initially or implement client-only fallbacks (e.g., manual text area with autosave).

Workspace/Outside records/Prompts
- Legacy `/workspace/*`, `/get_prompts`, `/load_one_liner_prompt`, `/load_health_summary_prompt` are not present. For MVP, load static templates from `templates/` or remove until equivalents are added.

Misc
- `load_full_chart` → Optional. If needed for background indexing, use `GET /api/patient/<dfn>/fullchart` (large payload) and only on demand.
- `vista_default_patient_list`, `vista_patient_search` → Not available; use a minimal DFN input UI for now.

## Phased refactor milestones

Phase 0 — Utilities and guards
- Add `ApiClient` helper (e.g., `static/js/api.js`) to centralize:
  - `getDFN()`/`setDFN(dfn)`; append DFN into `/api/patient/<dfn>/...` paths.
  - `csrfFetch` wrapper reuse; station/duz passthrough on the first call when present in URL or settings.
  - Common query building for `limit/next`, date filters (`last`, `start/stop`).
- Acceptance:
  - One-line calls like `ApiClient.quick('labs', { last: '6m' })` produce `GET /api/patient/<dfn>/quick/labs?start=...&stop=...`.

Phase 1 — Patient selection and switch
- Files: `static/selectpatient.js`, `static/patient_switch.js`.
- Replace server-side `/select_patient`, `/get_patient`, `/clear_session` calls with:
  - Set DFN locally (storage + URL param management).
  - Validate via `GET /api/patient/<dfn>/quick/demographics`.
  - Update UI header via returned demographics.
  - Remove CPRS sync calls (`/vista_rpc`) and sensitive checks for now.
- Acceptance:
  - Switching DFN updates header and triggers workspace tab refreshes without 5xx requests to missing endpoints.

Phase 2 — Documents/Notes/Radiology tabs
- Files: `static/workspace.js`, `static/workspace/modules/*documents*`, `templates/tabs/*`.
- Endpoint replacements:
  - Documents list: `GET /api/patient/<dfn>/list/documents?class=PROGRESS%20NOTES` for infinite scroll.
  - Detail/enriched: `GET /api/patient/<dfn>/quick/documents?class=...&includeText=1&includeEncounter=1` for focused views.
  - Radiology: `/quick/radiology` and `/list/radiology` similarly.
- Acceptance:
  - Documents tab loads and paginates with class/type filters; “open” shows text when available.

Phase 3 — Labs/Vitals/Meds
- Files: `static/workspace/modules/labs.js`, `static/workspace/modules/vitals.js`, `static/workspace/modules/meds.js` (or consolidated in `workspace.js`).
- Endpoint replacements:
  - `GET /api/patient/<dfn>/list/{labs|vitals|meds}` with `last` or `start/stop`.
  - Remove any client FileMan conversion; rely on server.
- Acceptance:
  - Tabs render with recent results, paging works, date filters honored.

Phase 4 — Problems/Allergies/Encounters
- Files: corresponding modules.
- Endpoint replacements:
  - `GET /api/patient/<dfn>/quick/{problems|allergies|encounters}` and add `status`/`includeComments` as needed.
- Acceptance:
  - Lists render correctly; optional filters function.

Phase 5 — AI “Hey OMAR”
- Files: `static/workspace/modules/heyomar.js`.
- Replace `/explore/notes_qa` with `POST /api/query/ask` and include `{ patient: { DFN } }`.
- Acceptance:
  - Basic Q&A returns `{ answer, citations }` from the default model.

Phase 6 — Note tab and Scribe (optional MVP)
- Files: `static/js/note.js`, `static/workspace/modules/note.js`.
- For MVP: disable live mic controls; allow manual note entry and autosave locally.
- If wiring scribe:
  - Create session → hold `session_id`.
  - Stream chunks → provider transcribes; poll status for `transcript`.
  - Stop on patient switch or user action.
- Acceptance:
  - Note tab usable without backend 404s; optional scribe shows accumulated transcript text when configured.

## De-scoped or postponed features

- CPRS integration (`/vista_rpc`, ORW* calls, default lists): out of scope.
- Sensitive record checks: out of scope; add UI-only banner if needed later.
- Prompt/template loaders and outside records workspace routes: add later or load from static assets.

## Risks and mitigations

- Large payloads if using `fullchart`: avoid by favoring tab-scoped `quick`/`list` endpoints.
- UI modules tightly coupled to legacy endpoints: mitigate by introducing `ApiClient` and refactoring module-by-module behind it.
- Mixed state between old and new flows during transition: add lightweight feature flags per tab for safe rollout.

## How to validate

- Manual
  - Set DFN in URL (?dfn=237) and confirm `GET /api/patient/237/quick/demographics` returns data.
  - Documents tab: infinite scroll via `/list/documents` and detail via `/quick/documents?includeText=1`.
  - Labs/Vitals/Meds: show recent with `last=6m`; pagination tokens advance.
  - Hey OMAR: `POST /api/query/ask` returns an answer.
- Automated
  - Keep existing `pytest` passing; add small JS smoke tests later if desired.

---

Appendix: Useful back-end routes (prefix `/api/patient/<dfn>`)
- Quick: `quick/{demographics, meds, labs, vitals, notes, documents, radiology, procedures, encounters, problems, allergies}`
- Lists: `list/{documents, labs, radiology, meds, vitals}`
- Raw: `vpr/<domain>`, `vpr/<domain>/item` (with `uid` or `id`)
- Compare: `compare/<domain>` (debug)
- Fullchart: `fullchart` (large)

AI
- `POST /api/query/ask` → `{ answer, citations, model_id }`

Scribe
- `POST /api/scribe/session`, `POST /api/scribe/stream?session_id=&seq=`, `GET /api/scribe/status?session_id=`, `POST /api/scribe/stop?session_id=`
