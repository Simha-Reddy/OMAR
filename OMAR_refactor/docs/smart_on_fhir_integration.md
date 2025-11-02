# SMART on FHIR integration (CDS Console)

This note summarizes how to run OMAR_refactor as a SMART-on-FHIR app inside the VA Clinical Decision Support (CDS) Console ("smart-on-fhir-container"). It’s based on the Console’s README (added under `Helpful Resources/README_for_CDS_SMART_on_FHIR_app_compliance.md`) and OMAR_refactor’s architecture.

## How the Console launches apps
- The Console launches your app via URL and adds `iss=<FHIR base>` and `launch=<base64 JSON>` query params.
- The launch payload encodes: `{ patient: <ICN>, sta3n: <station>, duz: <designated user> }` for single-patient apps. Multi-patient apps omit `patient`.
- It can also include `app_context=<base64>`; you must preserve this through auth redirects.
- Your app is registered in the Console via an entry in its `config/config-<env>.js` `APPLICATIONS` list (title, code, baseUrl, icon, flags). If embedded, consider `openLocation: 'embedded_tab'` and set `allowMicrophoneAccess: true` if you need mic (Scribe).

## App endpoints you need
- GET `/launch` (public): accepts `iss`, `launch`, and optional `app_context`. Starts SMART Authorization Code Flow (PKCE) against the `iss` FHIR server (Lighthouse Clinical FHIR).
- GET `/oauth/callback` (public): OAuth redirect URI to receive `code` and `state`. Exchanges for tokens and stores them server-side in the Flask session.
- Optional: window message listener on the client if `onCcowContextChange: 'send_message'` is configured; trigger server to refresh patient context.

## Auth flow (Lighthouse Clinical FHIR)
- Discover endpoints from `iss` (or configure explicitly): `/.well-known/smart-configuration` → `authorization_endpoint`, `token_endpoint`.
- Register a public client (no secret) with Lighthouse and set in `.env`:
  - `SMART_CLIENT_ID`, `SMART_REDIRECT_URI`, `SMART_SCOPES` (e.g., `launch/patient patient/*.read openid fhirUser offline_access`).
- Use PKCE and include SMART params in the authorize request: `aud=<iss>`, `launch=<encoded>`, `scope`, `client_id`, `redirect_uri`, `state`, `code_challenge`, `code_challenge_method=S256`.
- Persist/round-trip `app_context` via `state` or include it in your `redirect_uri` and carry into the post-auth landing route.

## Data access (server-side)
- Add a `FHIRDataGateway` (new) implementing `DataGateway` to fetch FHIR R4 resources with the SMART access token, mapping to existing quick shapes:
  - Demographics → `GET Patient/{id}` or `Patient?identifier=...|ICN`.
  - Meds → `MedicationRequest?patient=...` (consider `status`, `authoredon` date ranges).
  - Labs → `Observation?patient=...&category=laboratory`.
  - Vitals → `Observation?patient=...&category=vital-signs`.
  - Notes/Documents → `DocumentReference?patient=...` (use `presentedForm` or follow references; Composition/DiagnosticReport as needed).
  - Radiology → `DiagnosticReport?patient=...&category=radiology` (+ `ImagingStudy` if needed).
  - Problems → `Condition?patient=...`.
  - Allergies → `AllergyIntolerance?patient=...`.
  - Encounters → `Encounter?patient=...`.
- Convert your `start/stop/last` filters to FHIR search params and keep FileMan helpers for VPR mode; pick at runtime.

## RAG integration
- Reuse `RagEngine`, but extract text from FHIR `DocumentReference.presentedForm.data` (Base64) or `DiagnosticReport.conclusion/text`, `Composition.section.text`.
- Keep BM25-first; embeddings remain optional.

## Embedding, cookies, and CSP
- If the Console embeds your app (`openLocation: 'embedded_tab'`):
  - Frame embedding: change CSP `frame-ancestors` to allow the Console origin, e.g., `https://cds.med.va.gov` (configurable via env `EMBED_ORIGIN`).
  - Cookies: set `SESSION_COOKIE_SAMESITE=None` and `SESSION_COOKIE_SECURE=1` in deployed environments so cookies work in iframes over HTTPS.
  - CSRF: keep double-submit cookie; ensure it’s readable by client JS and header `X-CSRF-Token` is sent.
  - Microphone: if you need mic, coordinate with the Console using `allowMicrophoneAccess: true` in the app config.

## Minimal implementation plan
- Phase 1 (bootstrapping):
  - Add SMART auth blueprint (`/launch`, `/oauth/callback`).
  - Add `.env` keys below; confirm redirect works, token stored in session, and patient ICN parsed.
- Phase 2 (data path):
  - Implement `FHIRDataGateway` for demographics, vitals, labs. Add a feature flag `DATA_SOURCE=fhir|vpr`.
  - Add FHIR→quick transforms to match existing shapes so front-end remains unchanged.
- Phase 3 (documents & RAG):
  - Extend to documents/radiology/problems/allergies/encounters. Adapt RAG extraction for FHIR.
- Phase 4 (embed hardening):
  - Adjust CSP/frame-ancestors from env. Set cookie SameSite=None in production. Add optional `postMessage` handler for context changes.

## Environment variables (add to `.env`)
- SMART:
  - `SMART_CLIENT_ID=...`
  - `SMART_REDIRECT_URI=https://your.app/oauth/callback`
  - `SMART_SCOPES=launch/patient patient/*.read openid fhirUser offline_access`
- Runtime selection:
  - `DATA_SOURCE=vpr` (default) or `fhir`
- Embedding & cookies:
  - `EMBED_ORIGIN=https://cds.med.va.gov` (used to relax `frame-ancestors`)
  - `SESSION_COOKIE_SAMESITE=None` (prod in iframe) and `SESSION_COOKIE_SECURE=1`

## References
- Console README: `Helpful Resources/README_for_CDS_SMART_on_FHIR_app_compliance.md`
- Lighthouse Clinical Health API Authorization: https://developer.va.gov/explore/authorization/docs/authorization-code?api=clinical_health
- OMAR_refactor app factory/CSP: `OMAR_refactor/app/__init__.py`
- Service/gateway boundaries: `app/services/patient_service.py`, `app/gateways/*.py`
- Transforms & RAG: `app/services/transforms.py`, `app/query/services/{rag.py,rag_store.py}`
