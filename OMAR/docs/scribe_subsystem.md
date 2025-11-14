Scribe subsystem (audio transcription + note drafting)
=====================================================

Last updated: 2025-11-07

This was formerly `app/scribe/README.md`. Centralized here for consistency.

Overview
--------
Two complementary blueprints:
1. `/api/scribe/*` (audio ingestion + incremental transcript) — `app/scribe/blueprints/scribe_api.py`
2. `/scribe/*` (note drafting + refinement chat) — `app/scribe/blueprints/note_api.py`

High-level data flow
--------------------
Browser microphone → WAV/PCM chunk → POST `/api/scribe/stream` → transcription provider → transcript delta appended → ephemeral transcript state → UI polls or drafts note.

Key components
--------------
`providers.py`
- Provider abstraction.
- `DevEchoTranscriptionProvider` (development markers)
- `AzureSpeechTranscriptionProvider` (Azure Speech Short Audio REST API)
- `get_transcription_provider()` selects provider from env (`SCRIBE_TRANSCRIBE_PROVIDER=azure|dev`)

`blueprints/scribe_api.py` endpoints:
- `POST /api/scribe/session` → `{ session_id }`
- `POST /api/scribe/stream?session_id=...&seq=N`
- `GET /api/scribe/status?session_id=...`
- `GET /api/scribe/transcript?session_id=... | ?patient_id=...`
- `POST /api/scribe/stop?session_id=...`

Internals:
- Persists session metadata + transcript in Redis when available (`scribe:session:{id}`).
- Mirrors transcript deltas to ephemeral per-user+patient key (`ephemeral:state:{user_id}:{patient_id}`).
- Associates a `visit_id` when an open archive is present.
- Enforces monotonic `seq`; duplicates skipped with `{ ok: true, skipped: true }`.

`blueprints/note_api.py` endpoints:
- `POST /scribe/create_note`
- `POST /scribe/chat_feedback`
- Loads system preface from `prompts/scribe_system.md` (fallback hard-coded minimal message).
- Azure OpenAI Chat if configured; deterministic echo fallback otherwise.

Ephemeral transcript state
--------------------------
Redis JSON shape:
```json
{
  "transcript": "...",
  "last_seq": 17,
  "scribe_session_id": "<id>",
  "scribe_status": "active|stopped",
  "visit_id": "<archiveId or empty>",
  "updated_at": 1730832000.123,
  "created_at": 1730830500.456
}
```
TTL set by `EPHEMERAL_STATE_TTL`.

Sequence handling
-----------------
Apply chunk only if `seq > last_seq`. Resent/out-of-order chunks acknowledged but skipped.

Environment variables
---------------------
Transcription:
- `SCRIBE_TRANSCRIBE_PROVIDER` = `azure` | `dev` (default `dev`)
- `AZURE_SPEECH_KEY` / `AZURE_COG_SPEECH_KEY`
- `AZURE_SPEECH_REGION` or `AZURE_SPEECH_ENDPOINT`
- `SCRIBE_LANG` (default `en-US`)

Drafting (Azure OpenAI):
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT` (or `AZURE_ENDPOINT`)
- `AZURE_DEPLOYMENT_NAME`
- `AZURE_API_VERSION` (default `2024-02-15-preview`)

Session/ephemeral:
- `EPHEMERAL_STATE_TTL` (seconds; default 1800)

Security + CSRF
---------------
Global middleware handles CSRF double-submit cookie & headers; scribe endpoints rely on it.

Extending providers
-------------------
1. Subclass `TranscriptionProvider` in `providers.py`.
2. Add selection branch in `get_transcription_provider()`.
3. Return `TranscriptionResult(text=<str or None>, debug=<dict>)`.

Edge cases / resilience
-----------------------
| Case | Behavior |
|------|----------|
| Non-WAV for Azure | Skip, `text=None`, debug reason |
| Provider transient 5xx/429 | Retry w/ backoff; fallback `text=None` |
| Silence | `fallback:true`, no delta appended |
| Duplicate seq | `{ ok: true, skipped: true }` |
| Missing session | 404 JSON error |
| Patient mismatch | 409 conflict |

Local dev quick start
---------------------
1. Start server (Redis or fakeredis).
2. `POST /api/scribe/session { "patient_id": "123" }`
3. Stream WAV chunk: `/api/scribe/stream?session_id=...&seq=0` header `x-patient-id: 123`
4. Poll transcript: `/api/scribe/transcript?patient_id=123`
5. Draft note: `POST /scribe/create_note { transcript: "...", prompt: "SOAP" }`

Testing considerations
----------------------
Patch `get_transcription_provider()` to deterministic fake provider; assert idempotency and transcript accumulation.

Future enhancements
-------------------
- WebSocket streaming
- VAD & silence trimming
- Provider multiplexing w/ confidence scoring
- PHI redaction inline

Changelog note
--------------
Originally at `app/blueprints/scribe_api.py`; relocated under `app/scribe/` for cohesion.
