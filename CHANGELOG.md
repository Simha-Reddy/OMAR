# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2025-09-05

### Added
- Centralized, race-condition-safe Notes Ask submission flow in `static/explore/documents.js`:
  - `normalizeQuery()` for consistent text handling while preserving "show me" phrasing.
  - `submitNotesAsk()` as the single entry point for Notes Q&A requests with serialization, deduplication, debouncing, and cancellation.
  - `runNotesAskInternal()` that accepts an AbortSignal, validates request IDs, and safely updates UI only for the latest request.
- Debouncing for voice submissions (default 200ms) to avoid rapid duplicate requests when using wake phrase or mic button.
- Request deduplication using monotonic `notesAskRequestId` and `notesAskLastQuery`.
- Cancellation of in-flight requests via `AbortController` to prevent stale responses from updating the UI.
- Structured console logging with request IDs for easier debugging of request lifecycles.
- FHIR `[[...]]` placeholder resolution for Notes Ask queries before server submission.
- Linkification of inline citations in Notes QA responses, including ranges and multiple formats (e.g., `(Excerpts 2-4, 7)`).
- Demo masking support applied to Notes QA responses when enabled.
- **Enhanced Mobile Touch Support**: Improved touch event handling for iPhone and remote desktop compatibility:
  - Added `touchstart`, `touchend`, and `touchcancel` event handlers for Record and Hey Omar buttons
  - Implemented touch event priority over pointer/click events to prevent long-press → right-click issues
  - Added CSS enhancements for better touch responsiveness:
    - `touch-action: manipulation` to prevent iOS zoom on double-tap
    - `-webkit-touch-callout: none` to disable iOS Safari callouts
    - Visual feedback with `transform: scale(0.95)` on active touch
    - User selection prevention to avoid text highlighting on touch
    - Minimum 44px touch targets for accessibility compliance
- Feature flag `USE_TARGETED_RPCS` (default off) to toggle between full VPR bundle and targeted per-domain VistA RPCs.
- Initial targeted RPC support wired into `/select_patient` with safe fallbacks:
  - Problems via `ORQQPL PROBLEM LIST` (fallback `ORQQPL1 LIST`).
  - Allergies via `ORQQAL LIST` (fallback `ORQQAL PATIENT`).
  - Normalized to existing UI shapes; overrides VPR-derived indices only when available.
- Audio/transcription environment overrides in `.env`:
  - `CHUNKS_DIR`, `TRANSCRIPT_DIR`, `LIVE_TRANSCRIPT`, `TRANSCRIBE_WORKERS`, `TRANSCRIBE_SCAN_INTERVAL`.
- Transcription concurrency using a small thread pool and rename-based processing lock to avoid double-processing.
- Light telemetry:
  - Audio: queue depth and dropped callback frames.
  - Transcription: pending file count and per-chunk latency snapshots.

### Changed
- `runNotesAsk()` now routes through the centralized `submitNotesAsk()` to ensure consistent race condition handling across button clicks and Enter key submissions.
- Improved UI state management during Notes QA requests:
  - Disables/enables Ask button reliably.
  - Uses `aria-busy` on the answer container.
  - Updates status messages more consistently.
- Health Summary integration (Summary button) now reuses the Notes Ask flow and can prepend a one-line summary into `visitNotes` when requested.
- Mobile touch events take priority over pointer events to ensure reliable interaction on touch devices
- Enhanced Record button with comprehensive touch event support for better mobile reliability
- Audio capture stability in `record_audio.py`:
  - Shorter chunks (6s) with dynamic overlap (0.5s; trimmed to 0 when backlog grows).
  - Bounded queue with drop-oldest backpressure to prevent device overrun.
  - Higher input latency and explicit blocksize for resilience under CPU spikes.
  - WAV writes now use atomic write-then-rename to avoid partial reads by the consumer.
- Transcription worker in `monitor_transcription.py`:
  - Uses a shared `requests.Session`, request timeouts, and simple retry for 429/5xx.
  - Processes files with a small, configurable concurrency; locks each file via rename to `.processing.wav`.
- Labs pipeline: build lab list and secondary indexes (panels, LOINC index, summary) directly from VPR XML before discarding raw XML to reduce memory pressure and improve sort/grouping fidelity.

### Fixed
- Intermittent "show me" behavior caused by overlapping Notes QA requests (voice and typed). The new pipeline prevents:
  - Double-submits from rapid clicks/presses.
  - Out-of-order/stale responses updating the UI.
  - Races between voice submissions and typed asks.
- Improved error handling and user messaging (e.g., clear guidance when no patient is selected).
- **Mobile Touch Issues**: Resolved iPhone remote desktop compatibility problems where long presses triggered right-click context menus instead of normal button actions
- **Critical Event Object Bug**: Fixed bug where event objects were being passed as query text, causing "[object PointerEvent]" errors in Notes QA submissions
- Long-session transcription overflow/backlog issues: reduced input overflows and eliminated partial-file reads through backpressure and atomic handoff.
- Avoided duplicate/parallel processing of the same audio chunk via rename-based locking.

### Known follow-ups
- Finalize cleanup of legacy `submitAskText()` call path to remove any remaining duplicate logic and ensure all voice submissions go through `submitNotesAsk()` with debouncing.
- End-to-end testing with `run_local_server.py` and rapid interaction scenarios; verify request sequencing in the console logs.
- Extend targeted RPCs to vitals, medications, labs (direct ORWLRR), documents (TIU) and encounters (SDES/ORWCV) with per-domain timeouts and granular fallbacks.
- Document rollout guidance for `USE_TARGETED_RPCS` and add parity tests comparing RPC vs VPR for several patients.
- Revisit mic visualization (glow) implementation post MVP transcription stability.
