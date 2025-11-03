# OMAR Refactor — Changelog

All notable changes to this refactor scaffold will be documented in this file.

Format inspired by Keep a Changelog. Dates are in YYYY-MM-DD. For each change, prefer grouping under Added / Changed / Fixed / Removed / Security.

## [Unreleased]

### Added
- Lightweight ScribeRuntime event bus (`static/js/scribe_runtime.js`) to publish/consume transcript and recording status:
  - `ScribeRuntime.setStatus(active)` and `ScribeRuntime.onStatus(listener)`
  - `ScribeRuntime.setTranscript(text)` and `ScribeRuntime.onTranscript(listener)`
  - `ScribeRuntime.getStatus()` and `ScribeRuntime.getTranscript()` helpers

### Changed
- Centralized transcript access through `SessionManager.getTranscript()`; removed all fetches to `GET /scribe/live_transcript`.
- Centralized recording status through `SessionManager.getRecordingStatus()`; removed calls to `GET /scribe/recording_status`.
- Updated `static/js/app.js` to broadcast recording state via the ScribeRuntime event bus.
- `static/js/workspace/modules/note.js` and `static/js/workspace/modules/after_visit_summary.js` now rely solely on `SessionManager`/DOM for transcript (no legacy network fallbacks).
 - Workspace gating adjusted: Snapshot tab now renders even when no patient is selected; other tabs still require a patient.
 - Introduced frontend feature flags via `window.FEATURES` to disable deprecated endpoints (`sessionApi`, `layoutApi`, `getPatientApi`). When disabled, the client no longer calls `/load_session`, `/save_session`, `/workspace/layout`, or `/get_patient`.
 - Note module prompts loading is resilient: tries `/get_prompts`, falls back to `/static/prompts/default_prompts.json`, then a built-in default.

### Removed
- Deprecated usage of legacy endpoints: `live_transcript`, `set_live_transcript`, `clear_live_transcript`.
- Unused `static/js/scribe.js` (no longer referenced; superseded by Workspace modules). If needed for historical reference, retrieve from version control.
 - Removed deprecated `StaticChecks.js` and `SandboxRunner.js` includes from `templates/workspace.html` to eliminate 404s.
- Planned:
  - Port domain mappers (demographics, meds, labs, vitals, notes, radiology) from legacy code into `app/services/transforms.py`.
  - Add patient-context guard and audit writer for all PHI routes.
  - Replace prints with structured logging and correlation IDs; add basic metrics.
  - Extend tests: unit (services), integration (blueprints via test client), and gateway contract tests with fixtures.
  
### Added
- Extended `.env.example` with:
  - HOST/PORT overrides for waitress.
  - Azure OpenAI deployment names (`AZURE_DEPLOYMENT_NAME`, `AZURE_EMBEDDING_DEPLOYMENT_NAME`).
  - Azure Speech configuration (`AZURE_SPEECH_KEY`, `AZURE_SPEECH_ENDPOINT`).
- Transform layer `app/services/transforms.py` with direct VPR -> quick mappings (demographics, medications).
  - New endpoints: `/api/patient/<dfn>/quick/demographics` and `/api/patient/<dfn>/quick/meds`.
  - Raw VPR passthrough: `/api/patient/<dfn>/vpr/<domain>`.
  - Compare endpoint for diagnostics: `/api/patient/<dfn>/compare/<domain>`.
  - Standardized meds naming to `meds` (not `medications`):
    - Default VPR shortcut: `/api/patient/<dfn>/meds`.
    - Redirects: `/api/patient/<dfn>/medications` -> `/meds`, `/api/patient/<dfn>/quick/medications` -> `/quick/meds`.
- Added domains with consistent pattern (default VPR, quick, compare): labs, vitals, notes, radiology, procedures, encounters.
  - Extended with: problems, allergies.
  - Notes/Radiology/Procedures quick endpoints now support `includeText=1` (full text/report) and `includeEncounter=1` (visit metadata).
  - Problems quick endpoint supports `status=active|inactive|all` filtering and `includeComments=1`.
  - Unified documents endpoint: `GET /api/patient/<dfn>/quick/documents` with filters `class` and `type`, plus `includeText`, `includeEncounter`, `includeRaw` enrichment.
  - Default VPR documents shortcut: `GET /api/patient/<dfn>/documents` (VPR `documents`).

### Security
- Added optional `VISTA_API_SUPPRESS_TLS_WARNINGS` to silence `urllib3` InsecureRequestWarning only when `VISTA_API_VERIFY_SSL=false` (for local dev). Default is `0` (do not suppress). Prefer enabling SSL verification in `.env`.

### Removed
- Clinical Health API approach and any socket fallback: the project uses vista-api-x exclusively with `VPR GET PATIENT DATA JSON`.
- All FHIR transformation code and `/fhir/*` endpoints to preserve VA-specific fields and reduce complexity. Quick endpoints now map directly from VPR.
- Backward-compatibility redirects for medications removed (`/medications` and `/quick/medications`). Use `/meds` and `/quick/meds`.

### Changed
- Simplified `OMAR_refactor/.env` to only include keys required for the new approach (server basics, vista-api-x, Azure OpenAI + deployments, Azure Speech, and model temperatures). Removed legacy socket/feature-flag variables.
- Added inline comments to `OMAR_refactor/.env` explaining the purpose of each variable and production guidance.
 - `VistaApiXGateway` now uses `LHS RPC CONTEXT` by default (configurable via `VISTA_API_RPC_CONTEXT`, e.g., set to `CDSP RPC CONTEXT` when ready).

## [0.1.0] — 2025-10-28 — Scaffold created

### Added
- New folder `OMAR_refactor/` as a clean foundation to migrate features without Docker.
- Runtime and configuration:
  - `requirements.txt` — minimal server dependencies (Flask, Flask-Session, requests, redis/fakeredis, waitress, openai).
  - `.env.example` — server and vista-api-x configuration keys (FLASK_SECRET_KEY, VISTA_API_*).
  - `README.md` — quick start for Windows (PowerShell), how to run, and endpoint example.
  - `CHANGELOG.md` — this file; documents ongoing work.
- App factory and security:
  - `app/__init__.py` — Flask app factory with Redis/FakeRedis sessions, CSRF (double-submit cookie), and security headers.
  - Registers blueprints and injects CSRF token; defaults to local-friendly settings (set `SESSION_COOKIE_SECURE=1` for production HTTPS).
- Gateways and services:
  - `app/gateways/data_gateway.py` — `DataGateway` protocol and `GatewayError` base exception.
  - `app/gateways/vista_api_x_gateway.py` — vista-api-x HTTP client with JWT token fetch/refresh, basic retry/backoff, and SSL verify toggle via env.
  - `app/services/patient_service.py` — service layer bridging routes to gateway; initial `get_demographics` method.
- Blueprints and UI:
  - `app/blueprints/patient.py` — sample endpoint `GET /api/patient/<dfn>/demographics?station=500&duz=983` via `PatientService` + `VistaApiXGateway`.
  - `app/blueprints/general.py` — index route rendering a minimal landing page.
  - `templates/index.html` — simple page with a pointer to the sample API.
- Server runner and tests:
  - `run_server.py` — production-friendly waitress server on port 5050.
  - `tests/test_patient_service.py` — example unit test using a fake gateway.

### Notes
- This scaffold is Windows-friendly and does not require Docker. Use a real Redis or Memurai for multi-user sessions; FakeRedis is default for local dev.
- Future changes will be logged above under [Unreleased] and released in small, incremental versions.

