Scribe subsystem (audio transcription + note drafting)
===================================================

Overview
--------
The scribe feature is composed of two complementary blueprints:

1. `/api/scribe/*` (audio ingestion + incremental transcript)
	 Implemented in `app/scribe/blueprints/scribe_api.py`.
	 Handles creation of a scribe session, streaming audio chunks, live transcript accumulation, and stop events.

2. `/scribe/*` (note drafting + refinement chat)
	 Implemented in `app/scribe/blueprints/note_api.py`.
	 Converts the evolving transcript (plus an optional template/prompt and previous draft) into a structured clinical note and supports iterative refinement via chat-style feedback.

High-level data flow
--------------------
Client (browser) microphone -> chunk (WAV/PCM) -> POST `/api/scribe/stream` ->
transcription provider -> transcript delta appended -> ephemeral transcript state ->
frontend fetches transcript or passes it to `/scribe/create_note` for drafting.

Key components
--------------
`providers.py`
	Abstraction + implementations for audio chunk transcription.
	- `TranscriptionProvider` interface
	- `DevEchoTranscriptionProvider` (development fallback; emits small markers)
	- `AzureSpeechTranscriptionProvider` (Azure Speech Short Audio REST API)
	- `get_transcription_provider()` selects provider from env (`SCRIBE_TRANSCRIBE_PROVIDER=azure|dev`)

`blueprints/scribe_api.py`
	Endpoints:
	- `POST /api/scribe/session` -> `{ session_id }`
	- `POST /api/scribe/stream?session_id=...&seq=N` (binary audio body)
	- `GET  /api/scribe/status?session_id=...`
	- `GET  /api/scribe/transcript?session_id=... | ?patient_id=...`
	- `POST /api/scribe/stop?session_id=...`

	Internals:
	- Persists session metadata + transcript in Redis when available (key: `scribe:session:{id}`); falls back to in-memory dict for dev.
	- Mirrors (write-through) transcript deltas to an *ephemeral* per-user+patient state key (`ephemeral:state:{user_id}:{patient_id}`) with TTL (configured via `EPHEMERAL_STATE_TTL`).
	- Associates a `visit_id` when an open archive is present (key: `archive:open:{user_id}:{patient_id}`).
	- Enforces monotonic `seq` for idempotency; silently skips already processed or out-of-order chunks (client can resend safely).

`blueprints/note_api.py`
	Endpoints:
	- `POST /scribe/create_note` — Generates or refreshes a draft note from prompt + transcript + current draft.
	- `POST /scribe/chat_feedback` — Iterative refinement; client sends accumulated `messages` array including previous system/user/assistant turns.
	- Uses Azure OpenAI Chat if configured (env keys: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_DEPLOYMENT_NAME`); otherwise returns a deterministic synthesized echo for dev.
	- A system preface is loaded from `prompts/scribe_system.md` or a conservative hard-coded fallback.

Ephemeral transcript state
--------------------------
Why: The UI frequently polls for transcript progress even if a session id isn't continuously tracked (e.g., patient context switch). Storing the latest transcript per (user, patient) lets other UI modules access it without needing the session id.

Shape (JSON stored at Redis key `ephemeral:state:{user}:{patient}`):
```json
{
	"transcript": "... accumulated text ...",
	"last_seq": 17,
	"scribe_session_id": "<sessionId>",
	"scribe_status": "active|stopped",
	"visit_id": "<archiveId or empty>",
	"updated_at": 1730832000.123,
	"created_at": 1730830500.456
}
```

Sequence handling
-----------------
Clients increment `seq` per chunk starting at 0. The server only applies a chunk if `seq > last_seq`. Resent or duplicated chunks are acknowledged with `{ ok: true, skipped: true }` so clients can retry optimistically without branching logic.

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
Global CSRF middleware issues a double-submit cookie and checks header + cookie + session token for non-GET requests. The scribe endpoints rely on that middleware; they only perform lightweight patient guards.

Extending providers
-------------------
Add a new transcription provider:
1. Implement a subclass of `TranscriptionProvider` in `providers.py`.
2. Add selection logic inside `get_transcription_provider()` keyed by a new env value (e.g. `SCRIBE_TRANSCRIBE_PROVIDER=whisper`).
3. Ensure you return `TranscriptionResult(text=<string or None>, debug=<diagnostics dict>)`.

Edge cases / resilience
-----------------------
| Case | Behavior |
|------|----------|
| Non-WAV audio for Azure provider | Skipped with `text=None` and debug reason; no transcript delta appended |
| Provider transient 5xx / 429 | Retry with exponential backoff; falls back after retries to `text=None` |
| Silence (no recognized text) | Returns `fallback: true` but no delta appended |
| Duplicate seq | Returns `{ ok: true, skipped: true }` preserves idempotency |
| Missing session | 404 with JSON error |
| Patient mismatch | 409 conflict |

Local dev quick start
---------------------
1. Start server (ensuring Redis or fakeredis per config).
2. Create session:
	 `POST /api/scribe/session { "patient_id": "123" }`
3. Stream a small WAV chunk (seq=0) to `/api/scribe/stream?session_id=...&seq=0` with header `x-patient-id: 123`.
4. Poll transcript: `/api/scribe/transcript?patient_id=123`.
5. Draft note: `POST /scribe/create_note { transcript: "...", prompt: "SOAP" }`.

Testing considerations
----------------------
For unit tests, patch `get_transcription_provider()` to return a deterministic fake provider that emits fixed text so transcript accumulation and idempotency logic can be asserted without external calls.

Future enhancements (ideas)
---------------------------
* Streaming WebSocket endpoint (reduce polling latency).
* Adaptive chunk sizing & VAD integration to trim silence before upload.
* Provider multiplexing (send to two providers, reconcile + confidence scoring).
* Inline PHI filtering / redaction before storing transcript.

Changelog note
--------------
The ingestion blueprint formerly lived at `app/blueprints/scribe_api.py`; it was relocated to `app/scribe/blueprints/scribe_api.py` to align all scribe code under one package.

