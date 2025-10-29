OMAR Refactor (scaffold)

What this is
- A clean, minimal scaffold to grow OMAR into a multi-user server without Docker.
- Uses Flask app factory, Redis/FakeRedis sessions, CSRF, and a DataGateway for VistA access.

Run (Windows, local)
1) Create a virtualenv (recommended) and install requirements.txt
2) Copy .env.example to .env and set VISTA_API_* and VISTA_API_KEY
3) Run: `python run_server.py` (serves on http://127.0.0.1:5050)

Sample endpoint
- GET /api/patient/<dfn>/demographics?station=500&duz=983

Notes
- This scaffold prefers vista-api-x (no socket). Socket fallback can be added as another Gateway.
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
