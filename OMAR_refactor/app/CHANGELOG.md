# OMAR Refactor — Changelog

All notable changes to this refactor scaffold will be documented in this file.

Format inspired by Keep a Changelog. Dates are in YYYY-MM-DD. For each change, prefer grouping under Added / Changed / Fixed / Removed / Security.

## [2025-11-03] — Phase 5 (Legacy client archive removal + strict storage allowlist)

### Added
- Strict localStorage allowlist enforcement on startup to prevent any non-approved keys from persisting. Only non-PHI preferences remain (theme, CPRS sync flags, and auto-archive toggles as a fallback).
- Server endpoint to delete archives: `DELETE /api/archive/delete?id=...` (verifies user ownership, clears open-id cache if applicable).

### Changed
- `static/js/archive.js` is now fully server-backed: lists with `GET /api/archive/list`, restores with `GET /api/archive/load`. Delete is disabled until a server endpoint exists.
  - Delete is now enabled in the UI and uses the new server endpoint. Bulk delete loops over IDs client-side.
- `static/js/app.js` endSession action now saves to server archives (no client-local writes) and reloads the app.
- Exposed `window.saveArchiveNow()` for reuse in flows (used by patient switch pre-purge save).

### Removed
- Deprecated client-local archive methods in `SessionManager` (`saveFullSession`, `loadSavedSession`, `listSessions`, `deleteSession`, `endSession`) now no-op with warnings to avoid PHI persistence in the browser.

### Notes
- Combined with earlier phases, the client no longer persists PHI in browser storage. Session state and archives live on the server (plaintext JSON, per constraints).

## [2025-11-03] — Phase 4 (Auto-archive & settings)

### Added
- Server-backed auto-archive preference with UI toggle:
  - `GET /api/archive/auto-archive/status` to read, `POST /api/archive/auto-archive/toggle` to set per-user.
  - `static/js/settings.js` reads status on load and persists changes to the server, keeping a local mirror as fallback.
- Background auto-archive (every 5 seconds) when enabled and a patient is active:
  - `static/js/app.js` collects session state via `SessionManager.collectData()` and posts to `POST /api/archive/save` with the current patient_id.
  - Lightweight state signature avoids redundant saves when there is no content change; always attempts a final save on page unload.
- Event-based saves:
  - On recording stop, a save is triggered.
  - On patient switch start, a save is triggered before purge (in `patient_switch.js`).

### Changed
- Auto-archive has moved from legacy client-local storage to server archives.
- `startAutoSaveLoop` now respects the server preference; default is server `AUTO_ARCHIVE_DEFAULT` when no user override.

### Notes
- Archives remain plaintext JSON on the server (no encryption), per the privacy constraints.
- The server caches/open-id behavior is managed automatically by `POST /api/archive/save` (creating an archive if none is open).

## [2025-11-03] — Phase 3 (Patient switch purge + reload archive prompt)

### Added
- On patient switch, the client now purges server-side ephemeral state for the previous patient via `POST /api/session/purge` to prevent PHI carryover.
- After a successful switch to the new patient, the client queries `GET /api/archive/list?patient_id=...` and, if any archive exists, prompts the user to reload the most recent archive. On acceptance, it loads via `GET /api/archive/load?id=...`, restores into the UI, and immediately persists the state back to the ephemeral session.

### Changed
- `static/js/patient_switch.js` orchestrates the above flow with minimal UI disruption, stopping scribe, blanking layout, rehydrating, updating headers, and then offering the reload prompt.

### Notes
- Archives remain plaintext JSON on the server (no encryption), per prior instruction.
- The ephemeral session for the new patient starts empty; if the user chooses to reload an archive, it becomes the working state.

## [2025-11-03] — Phase 1 (Backend state API + archives)

### Added
- New ephemeral session state API (`/api/session`):
  - `GET /api/session/state?patient_id=...` — returns the current in-memory state for the user + patient.
  - `POST /api/session/state` — upserts partial state: `transcript`, `draftNote`, `to_dos`, `patientInstructions`, `heyOmarQueries`.
  - `POST /api/session/purge` — deletes the ephemeral state for the patient.
  - Uses Redis with TTL (default 1800s) when available; falls back to in-process store for local dev.
- New archive API (`/api/archive`):
  - `POST /start` — creates a new archive and returns `archive_id`.
  - `POST /save` — saves a snapshot (creates if needed, or uses the last open archive id).
  - `GET /list?patient_id=...` — lists archives for the user + patient.
  - `GET /load?id=...` — loads a specific archive document.
  - `POST /auto-archive/toggle` and `GET /auto-archive/status` — per-user auto-archive preference (defaults to server flag `AUTO_ARCHIVE_DEFAULT`).
  - Archives are plaintext JSON files (no encryption per instruction) under `OMAR_refactor/archives/`.
- Scribe write-through: transcript deltas from `/api/scribe/stream` now append to the ephemeral session state for the active user + patient.

### Configuration
- `EPHEMERAL_STATE_TTL` environment variable controls TTL (seconds) for ephemeral session state and the cached "open archive id"; default 1800.

### Notes
- This phase introduces server primitives only; the frontend will start using them in Phase 2 when we remove client localStorage autosave.

## [2025-11-03] — Phase 2 (Frontend SessionManager → server state)

### Changed
- `static/js/SessionManager.js` now saves and loads session state from the server (no localStorage autosave):
  - `POST /api/session/state` with fields: `transcript`, `draftNote`, `to_dos`, `patientInstructions`, `heyOmarQueries`.
  - `GET /api/session/state?patient_id=...` to restore.
  - `POST /api/session/purge` to clear on demand.
- Renamed and consolidated fields in the client state shape:
  - `transcript` (was scribe.transcript)
  - `draftNote` (was scribe.feedbackReply)
  - `to_dos` (was scribe.checklist)
  - `patientInstructions` (unchanged key but moved to top-level)
  - `heyOmarQueries` (placeholder for future module history)
- Removed Explore-related save/restore paths from SessionManager.

### Notes
- CSRF is attached automatically via the global fetch patch. Patient ID uses DFN from `window.Api.getDFN()` or sessionStorage fallback.
- Archive behavior is unchanged in this phase; auto-archive will migrate to server in Phase 4.

## [2025-11-03] — Phase 0 (Privacy prep and guard rails)

### Added
- Startup scrub in `static/js/app.js` to remove legacy PHI persisted in the browser from prior builds:
  - Deletes `session:last`, all `session:archive:*`, `workspace_feedback_reply` and `workspace_feedback_reply:*`, and any `explore:` / `exploreQAHistory:` keys.
  - Leaves non-PHI preferences (e.g., theme) intact.
- Feature flags in `app/__init__.py` to support the phased rollout:
  - `EPHEMERAL_SERVER_STATE` (default ON)
  - `AUTO_ARCHIVE_DEFAULT` (default ON)

### Notes
- No server routes or data flows changed in this phase; this is a safe, defensive cleanup that prevents legacy client persistence from lingering.
- Next (Phase 1): add backend endpoints for ephemeral session state and server-side archives, and wire scribe transcript write-through.

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

