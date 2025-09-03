# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2025-09-03

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

### Changed
- `runNotesAsk()` now routes through the centralized `submitNotesAsk()` to ensure consistent race condition handling across button clicks and Enter key submissions.
- Improved UI state management during Notes QA requests:
  - Disables/enables Ask button reliably.
  - Uses `aria-busy` on the answer container.
  - Updates status messages more consistently.
- Health Summary integration (Summary button) now reuses the Notes Ask flow and can prepend a one-line summary into `visitNotes` when requested.
- Mobile touch events take priority over pointer events to ensure reliable interaction on touch devices
- Enhanced Record button with comprehensive touch event support for better mobile reliability

### Fixed
- Intermittent "show me" behavior caused by overlapping Notes QA requests (voice and typed). The new pipeline prevents:
  - Double-submits from rapid clicks/presses.
  - Out-of-order/stale responses updating the UI.
  - Races between voice submissions and typed asks.
- Improved error handling and user messaging (e.g., clear guidance when no patient is selected).
- **Mobile Touch Issues**: Resolved iPhone remote desktop compatibility problems where long presses triggered right-click context menus instead of normal button actions
- **Critical Event Object Bug**: Fixed bug where event objects were being passed as query text, causing "[object PointerEvent]" errors in Notes QA submissions

### Known follow-ups
- Finalize cleanup of legacy `submitAskText()` call path to remove any remaining duplicate logic and ensure all voice submissions go through `submitNotesAsk()` with debouncing.
- End-to-end testing with `run_local_server.py` and rapid interaction scenarios; verify request sequencing in the console logs.
