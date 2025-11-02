OMAR Refactor (scaffold)

What this is
- A clean, minimal scaffold to grow OMAR into a multi-user server without Docker.
- Uses Flask app factory, Redis/FakeRedis sessions, CSRF, and a DataGateway for VistA access via vista-api-x only.

Run (Windows, local)
1) Create a virtualenv (recommended) and install requirements.txt
2) Copy .env.example to .env and set VISTA_API_* and VISTA_API_KEY
3) Run: `python run_server.py` (serves on http://127.0.0.1:5050)

Sample endpoint
- GET /api/patient/<dfn>/demographics?station=500&duz=983

Notes
- This scaffold uses vista-api-x exclusively and calls the VPR GET PATIENT DATA JSON RPC. By default it uses the LHS RPC CONTEXT (configurable via `VISTA_API_RPC_CONTEXT`); you can switch to CDSP later by changing the env.
- For sessions, FakeRedis is default. Set USE_FAKEREDIS=0 to use a real Redis/Memurai.

## Endpoints and domain aliases

Base prefix: `/api/patient/<dfn>` (optionally include `?station=<sta>&duz=<duz>`)

Default VPR shortcuts (raw, unmodified):
- `GET /demographics` (alias of VPR `patient`)
- `GET /meds`
- `GET /labs`
- `GET /vitals`
- `GET /documents` (VPR `documents`)
- `GET /radiology`
- `GET /procedures`
- `GET /encounters` (alias of VPR `visits`)
- `GET /problems`
- `GET /allergies`

Quick transformed shapes (UI-friendly):
- `GET /quick/demographics`
- `GET /quick/meds`
- `GET /quick/labs`
- `GET /quick/vitals`
- `GET /quick/documents` (unified: Progress Notes, Radiology Reports, Surgical Reports, Discharge Summaries)
- `GET /quick/radiology`
- `GET /quick/procedures`
- `GET /quick/encounters`
- `GET /quick/problems`
- `GET /quick/allergies`

Diagnostics:
- Raw passthrough: `GET /vpr/<domain>`
- Compare raw vs quick: `GET /compare/<domain>`

`includeRaw` support for quick endpoints:
- Append `?includeRaw=1` to attach the corresponding raw VPR item to each quick item as `_raw` (best-effort by index). For demographics, attaches the first raw item.

Extra query parameters:
- Documents, Notes, Radiology, Procedures:
	- `includeText=1` to include full text/report when available (notes body, radiology report/impression, procedure narrative).
	- `includeEncounter=1` to include encounter metadata `{ visitUid, date, location }` when available.
- Problems:
	- `status=active|inactive|all` to filter items (default: `all`).
	- `includeComments=1` to include problem comments (date, author, text) when available.

Unified documents filters (for `/quick/documents`):
- `class` one or more document classes (comma-separated; case-insensitive), e.g. `PROGRESS NOTES`, `RADIOLOGY REPORTS`, `SURGICAL REPORTS`, `DISCHARGE SUMMARY`.
- `type` one or more document type names or codes (comma-separated; case-insensitive), e.g. `Progress Note` or `PN`, `Radiology Report` or `RA`, `Surgery Report` or `SR`, `Discharge Summary` or `DS`.

Domain alias mapping (route -> VPR domain):
- `demographics` -> `patient`
- `documents` -> `documents`
- `encounters` -> `visits`
- `meds` -> `meds`
- `labs` -> `labs`
- `vitals` -> `vitals`
- `radiology` -> `radiology`
- `procedures` -> `procedures`
- `problems` -> `problems`
- `allergies` -> `allergies`

Removed backward-compatibility redirects:
- `/medications` and `/quick/medications` redirects have been removed in favor of `/meds` and `/quick/meds`.

## New backend folders for AI and features

To make it easy for multiple developers to work on AI features, the code is organized into three clear areas:

- `app/ai_tools/` — shared utilities for AI work (embeddings, LLM helpers). Reusable across Query and Scribe.
- `app/query/` — everything related to “Hey OMAR” (RAG and answering questions):
	- `blueprints/query_api.py` — POST `/api/query/ask` receives `{ prompt, model_id }` and returns `{ answer, citations, provider_id }`.
	- `registry.py` — finds and validates providers.
	- `contracts.py` — standard interface that providers implement.
	- `providers/default/` — the current Hey OMAR model implementation.
	- `providers/template_provider/` — a copy-ready template with a short README on how to make your own.
- `app/scribe/` — speech-to-text and note-drafting utilities and endpoints:
	- `blueprints/scribe_api.py` — endpoints for uploading/streaming audio (stub to start).
	- `prompts/` — scribe prompts in `.md` files instead of hard-coded strings.

All prompts used by providers or scribe are stored as `.md` files for clarity and easy editing.

## Front-end structure and shared styles

We’re standardizing styles so the app feels consistent and easy to extend:

- `static/styles/theme.css` — shared colors, buttons, tables, spacing, and a small loading-spinner utility.
- `static/js/ui.js` — shared UI helpers (showLoading, hideLoading, toast messages) and CSRF-aware fetch.
- Each tab may include a small CSS file for its unique tweaks.
- `templates/tabs/template_tab.html` — a minimal starter tab with instructions for developers.
