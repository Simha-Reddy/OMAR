# Safe Modules Sandbox Policy (v1)

This policy governs untrusted render_code executed in the Agent sandbox. All code is treated as untrusted. Only capability objects are available.

Banned APIs (must be rejected by static checks and blocked at runtime):
- eval, Function constructor
- import(), dynamic import, require
- fetch, XMLHttpRequest, navigator.sendBeacon
- WebSocket, EventSource
- Worker, SharedWorker, ServiceWorker, SharedArrayBuffer, Atomics
- postMessage (except via provided parent helper), BroadcastChannel
- setTimeout, setInterval, setImmediate, requestAnimationFrame
- localStorage, sessionStorage, indexedDB, caches
- document.cookie, document.domain
- window.top, window.opener, window.parent (except size ping helper)
- navigation, location changes, window.open
- addEventListener on window/document not allowed; no inline event handlers

Iframe and CSP requirements:
- <iframe sandbox="allow-scripts"> only
- strict CSP: default-src 'none'; script-src 'unsafe-inline'; connect-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'
- disallow navigation by intercepting window.open and assignments to location
- origin isolation when available (Cross-Origin-Opener-Policy, Cross-Origin-Embedder-Policy)

Capabilities provided (frozen objects):
- Tabulator: wrapper to create read-only tables in a provided container
- SimplePlots: minimal canvas plotting (lines, points, axes)
- Formatter: helpers for units, dates, reference ranges

Allowed module interface:
- The LLM produces a JS module body: function render({datasets, container, Tabulator, SimplePlots, Formatter}) { /* ... */ }
- No top-level variables outside the function scope.
- Must render only inside the provided container.
- Return value optional; may call a provided resize() helper to auto-adjust height.

Budgets and execution limits:
- Soft byte cap on code size (e.g., <= 20 KB)
- Runtime cutoff via cooperative timer guard (e.g., 50 ms budget) and instruction counting
- Dataset row/byte caps enforced on server; sandbox only receives allowed data

Prompt-injection defense:
- Stage A planning prompt includes no raw clinical note text
- Summaries must be derived from returned datasets or explicitly approved fields
- All text rendered is considered untrusted and must be escaped where relevant

Audit logging:
- Persist plan hash, tool usage, dataset sizes, timing, user approver
- Record truncation/clamping events and any static-check rejections
