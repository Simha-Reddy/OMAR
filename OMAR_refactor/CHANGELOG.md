# OMAR Refactor — Changelog

All notable changes to this refactor scaffold will be documented in this file.

Format inspired by Keep a Changelog. Dates are in YYYY-MM-DD. For each change, prefer grouping under Added / Changed / Fixed / Removed / Security.

## [Unreleased]
- Planned:
  - Port domain mappers (demographics, meds, labs, vitals, notes, radiology) from legacy code into `app/services/transforms.py`.
  - Add patient-context guard and audit writer for all PHI routes.
  - Replace prints with structured logging and correlation IDs; add basic metrics.
  - Extend tests: unit (services), integration (blueprints via test client), and gateway contract tests with fixtures.
  
### Added
- Tests: `pytest.ini` registering the `integration` mark to silence pytest warnings and clearly separate live/external tests.
- Server launcher: `Start_OMAR.bat` now uses the embedded interpreter at `OMAR/python/python.exe` and launches the refactor server `OMAR_refactor/run_server.py`.
- API: Introduced a paginated list envelope for documents at `GET /api/patient/<dfn>/list/documents`.
  - Returns `{ items: T[], next: string|null, total: number }`.
  - Supports the same filters as `/quick/documents` (`class`, `type`) but omits heavy enrichments by default for performance.
  - The `next` token is an opaque integer offset for now; clients pass it back as `?next=` to continue.
 - API: Added `GET /api/patient/<dfn>/fullchart` to fetch the full VPR JSON without a domain filter.
   - This forwards `VPR GET PATIENT DATA JSON` with a namedArray containing only `patientId`.
   - Warning: payloads can be very large; prefer domain endpoints with `start/stop` filters when possible.
 - API: Expanded raw VPR endpoints and pass-through filters per VPR 1.0 JSON domains:
   - New endpoints: `/appointments`, `/orders`, `/consults`, `/immunizations`, `/cpt`, `/exams`, `/education`, `/factors`, `/pov`, `/skin`, `/observations`, `/ptf`, `/surgery`, `/image`.
   - Existing endpoints updated with pass-through filters where applicable:
     - documents/document: `start, stop, max, id, uid, status, category, text, nowrap`
     - labs/lab: `start, stop, max, id, uid, category (CH|MI|AP), nowrap`
     - meds/med: `start, stop, max, id, uid, vaType (I|O|N)`
     - vitals/vital: `start, stop, max, id, uid`
     - radiology/image, procedures/procedure, encounters/visit: `start, stop, max, id, uid`
     - problems/problem: `max, id, uid, status (A|I)`
   - Each endpoint forwards the recognized query params into the VPR namedArray for `VPR GET PATIENT DATA JSON`.
 - Utils: Added `to_fileman_datetime` converter. `start`/`stop` query params can be provided as ISO (YYYY-MM-DD or YYYY-MM-DDTHH:MM[:SS][Z]) or `yyyymmdd[HHMM[SS]]`; they are converted to FileMan (`YYYMMDD[.HHMM[SS]]`) automatically.
 - API: Added list-envelope endpoints:
   - `GET /api/patient/<dfn>/list/labs` → returns quick-mapped labs with `{items,next,total}` and optional `includeRaw=1`.
   - `GET /api/patient/<dfn>/list/radiology` → returns quick-mapped radiology with `{items,next,total}` and optional `includeRaw=1`.
  - `GET /api/patient/<dfn>/list/meds` → returns quick-mapped meds with `{items,next,total}` and optional `includeRaw=1`.
  - `GET /api/patient/<dfn>/list/vitals` → returns quick-mapped vitals with `{items,next,total}` and optional `includeRaw=1`.
 - API: Single-item drilldown for any domain:
   - `GET /api/patient/<dfn>/vpr/<domain>/item?uid=...` (or `?id=...`) forwards filters to VPR and returns the matching item(s).
 - Utils: Relative date convenience for filters:
   - `last=14d|2w|6m|1y` accepted on endpoints that support `start/stop` and will resolve to a start/stop FileMan range when not explicitly set.
 - Transforms: FileMan → ISO conversion in quick outputs:
   - All quick mappers now normalize date/time fields from FileMan (`YYYMMDD[.HHMM[SS]]`) to ISO8601 `...Z`.
- Scribe (note) pipeline skeleton end-to-end:
  - Backend blueprint `app/blueprints/scribe_api.py` with endpoints:
    - `POST /api/scribe/session` → start session (patient-scoped)
    - `POST /api/scribe/stream?session_id=&seq=` → accept audio chunks with CSRF + patient guard; idempotent on (session_id, seq)
    - `GET /api/scribe/status?session_id=` → live transcript
    - `POST /api/scribe/stop?session_id=` → finalize
  - Pluggable transcription providers `app/scribe/providers.py`:
    - `AzureSpeechTranscriptionProvider` (Short Audio REST; WAV recommended) — configured by `SCRIBE_TRANSCRIBE_PROVIDER=azure`, `AZURE_SPEECH_KEY`, plus `AZURE_SPEECH_REGION` or `AZURE_SPEECH_ENDPOINT`; `SCRIBE_LANG` defaults to `en-US`.
    - `DevEchoTranscriptionProvider` (no external calls) — default when Azure not configured.
  - Frontend Note tab `templates/tabs/note.html` and recorder `static/js/note.js`:
    - Consent gate, start/stop, red indicator, CSRF-aware chunk uploads every ~2s.
    - Safari-safe WAV fallback (WebAudio → PCM16 WAV per chunk). Opus via MediaRecorder used when not forcing WAV.
  - Security: CSRF double-submit honored; patient isolation enforced on every chunk; no audio persisted server-side.
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
- Corrected VPR JSON domain tokens to match the VPR 1.0 Developer's Guide (singular tokens):
  - meds→med, labs→lab, vitals→vital, notes/documents→document, radiology→image, procedures→procedure, encounters→visit, problems→problem, allergies→allergy.
  - Kept common plural aliases for backward compatibility at the service layer.
  - Updated documents default VPR route to use `document`.
- No feature flag is used for selecting vista-api-x: all reads go through vista-api-x unconditionally for simplicity and clarity.
- Simplified `OMAR_refactor/.env` to only include keys required for the new approach (server basics, vista-api-x, Azure OpenAI + deployments, Azure Speech, and model temperatures). Removed legacy socket/feature-flag variables.
- Added inline comments to `OMAR_refactor/.env` explaining the purpose of each variable and production guidance.
- Refined date handling: `_parse_any_datetime_to_iso` recognizes FileMan in addition to ISO and `yyyymmdd[HHMM[SS]]`, ensuring quick outputs consistently return ISO.
 - `VistaApiXGateway` now uses `LHS RPC CONTEXT` by default (configurable via `VISTA_API_RPC_CONTEXT`, e.g., set to `CDSP RPC CONTEXT` when ready).
 - Renamed `app/query/providers/` → `app/query/query_models/` and updated discovery/imports, tests, and docs. Terminology now uses “query model” instead of “provider”. API response now returns `model_id` (was `provider_id`). Contract renamed from `ModelProvider` → `QueryModel`.
 - Blueprint registration in `app/__init__.py` cleaned up to avoid duplicate imports/registrations and make scribe optional.

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

