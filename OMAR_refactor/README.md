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
Default VPR shortcuts (raw, pass-through filters supported):
- `GET /demographics` → VPR domain `patient`
- `GET /documents` → VPR domain `document` (supports text=1, status, category, start, stop, max, id, uid, nowrap)
- `GET /meds` → `med` (supports start, stop, max, id, uid, vaType=I|O|N)
- `GET /labs` → `lab` (supports start, stop, max, id, uid, category=CH|MI|AP, nowrap)
- `GET /vitals` → `vital` (supports start, stop, max, id, uid)
- `GET /radiology` → `image` (supports start, stop, max, id, uid)
- `GET /procedures` → `procedure` (supports start, stop, max, id, uid)
- `GET /encounters` → `visit` (supports start, stop, max, id, uid)
- `GET /problems` → `problem` (supports max, id, uid, status=A|I)
- `GET /allergies` → `allergy` (supports start, stop, max, id, uid)

Additional raw VPR domains:
- `GET /appointments` → `appointment` (supports start, stop, max, id, uid)
- `GET /orders` → `order` (supports start, stop, max, id, uid)
- `GET /consults` → `consult` (supports start, stop, max, id, uid, nowrap)
- `GET /immunizations` → `immunization` (supports start, stop, max, id, uid)
- `GET /cpt` → `cpt` (supports start, stop, max, id, uid)
- `GET /exams` → `exam` (supports start, stop, max, id, uid)
- `GET /education` → `education` (supports start, stop, max, id, uid)
- `GET /factors` → `factor` (supports start, stop, max, id, uid)
- `GET /pov` → `pov` (supports start, stop, max, id, uid)
- `GET /skin` → `skin` (supports start, stop, max, id, uid)
- `GET /observations` → `obs` (supports start, stop, max, id, uid)
- `GET /ptf` → `ptf` (supports start, stop, max, id, uid)
- `GET /image` → `image` (same as `/radiology`)

Date filters and FileMan conversion:
- For `start`/`stop` you can pass either FileMan values directly (e.g., `3251029` or `3251029.1430`) or common date/time formats and we will convert:
	- ISO date/time: `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM[:SS][Z]`
	- Digits: `yyyymmdd[HHMM[SS]]`
	- We convert to FileMan `YYYMMDD[.HHMM[SS]]` where `YYY = year - 1700`.
	- Convenience: pass `last=14d|2w|6m|1y` and we’ll compute `start`/`stop` when not provided (months≈30 days, years≈365 days).

	Pagination envelopes for infinite scroll:
	- Endpoints return `{ items, next, total }` and accept `limit` and `next` (or `offset`) for paging:
		- `GET /list/documents`, `/list/labs`, `/list/radiology`, `/list/meds`, `/list/vitals`.
		- Optional `includeRaw=1` pairs quick items with corresponding raw VPR items.

Single-item drill-down and list envelopes:
- `GET /vpr/<domain>/item?uid=...` (or `?id=...`) returns a single item by UID or ID across domains.
- List envelope endpoints return `{ items, next, total }` for infinite-scroll UIs:
  - `GET /list/documents`, `/list/labs`, `/list/radiology`, `/list/meds`, `/list/vitals`.
  - Optional `includeRaw=1` to pair each quick item with its raw VPR item.

Quick transformed shapes (UI-friendly):
Domain alias mapping (route -> VPR domain):
- `demographics` → `patient`
- `documents`/`notes` → `document`
- `encounters`/`visits` → `visit`
- `meds` → `med`
- `labs` → `lab`
- `vitals` → `vital`
- `radiology`/`image` → `image`
- `procedures` → `procedure`
- `problems` → `problem`
- `allergies` → `allergy`
- `appointments` → `appointment`
- `orders` → `order`
- `consults` → `consult`
- `immunizations` → `immunization`
- `cpt` → `cpt`, `exams` → `exam`, `education` → `education`
- `factors` → `factor`, `pov` → `pov`, `skin` → `skin`, `observations` → `obs`
- `ptf` → `ptf`

Diagnostics:
- Raw passthrough: `GET /vpr/<domain>`
- Compare raw vs quick: `GET /compare/<domain>`
- Full chart: `GET /fullchart` (calls VPR with only `patientId`; can be a very large payload)

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

Removed backward-compatibility redirects:
- `/medications` and `/quick/medications` redirects have been removed in favor of `/meds` and `/quick/meds`.

Session-bound station/duz:
- The backend binds the VistA site (station) and user (duz) to the session. You can:
	- Provide `?station=500&duz=983` on any request once; they’ll persist in session for subsequent calls.
	- Defaults can be set via env `DEFAULT_STATION` and `DEFAULT_DUZ` (fall back to 500/983).

## New backend folders for AI and features

To make it easy for multiple developers to work on AI features, the code is organized into three clear areas:

- `app/ai_tools/` — shared utilities for AI work (embeddings, LLM helpers). Reusable across Query and Scribe.
- `app/query/` — everything related to “Hey OMAR” (RAG and answering questions):
	- `blueprints/query_api.py` — POST `/api/query/ask` receives `{ prompt, model_id }` and returns `{ answer, citations, model_id }`.
	- `registry.py` — discovers and validates query models.
	- `contracts.py` — standard interface that query models implement.
	- `query_models/default/` — the current Hey OMAR model implementation.
	- `query_models/template_model/` — a copy-ready template with a short README on how to make your own.
- `app/scribe/` — speech-to-text and note-drafting utilities and endpoints:
	- `blueprints/scribe_api.py` — endpoints for uploading/streaming audio (stub to start).
	- `prompts/` — scribe prompts in `.md` files instead of hard-coded strings.

All prompts used by query models or scribe are stored as `.md` files for clarity and easy editing.

## Front-end structure and shared styles

We’re standardizing styles so the app feels consistent and easy to extend:

- `static/styles/theme.css` — shared colors, buttons, tables, spacing, and a small loading-spinner utility.
- `static/js/ui.js` — shared UI helpers (showLoading, hideLoading, toast messages) and CSRF-aware fetch.
- Each tab may include a small CSS file for its unique tweaks.
- `templates/tabs/template_tab.html` — a minimal starter tab with instructions for developers.
