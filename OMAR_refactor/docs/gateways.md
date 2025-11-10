# Gateways: vista-api-x (DEMO) and VistA Socket

Last updated: 2025-11-07

This refactor supports two backend gateway modes:

- DEMO (HTTP): Uses vista-api-x over HTTPS. No ACCESS/VERIFY required.
- Socket (Broker): Direct VistA RPC broker connection. Requires ACCESS/VERIFY and a cipher table.

## Selecting a site and logging in

The landing page should call:

- GET /api/sites → returns a list of sites including a DEMO option
- POST /api/login → body { siteKey, access?, verify?, context? }
  - DEMO: set `siteKey=demo` (no credentials)
  - Socket sites: provide ACCESS/VERIFY; optional `context` defaults to `OR CPRS GUI CHART`
- POST /api/logout → closes socket session and clears mode

Once logged in, APIs under `/api/patient/*` and patient search routes automatically use the active gateway via the factory.

## Environments

Required for socket mode:

- `OMAR_SITES`: e.g. `Puget Sound|127.0.0.1|9200; Boise|10.0.0.12|9200`
- `VISTARPC_CIPHER_FILE`: absolute path to `cipher.txt` containing cipher rows (or `VISTARPC_CIPHER` inline)
- `VISTA_DEFAULT_CONTEXT` (optional): defaults to `OR CPRS GUI CHART`
- `VISTA_VPR_XML_CONTEXT` (optional): if set, overrides the single context used for VPR XML; defaults hard-coded to `JLV WEB SERVICES` (no fallback iteration).

The DEMO mode uses the existing vista-api-x envs (`VISTA_API_BASE_URL`, `VISTA_API_KEY`, etc.).

## Patient data in socket mode

`LHS RPC CONTEXT` (JSON VPR) is typically not available locally. We now use ONLY:

- `JLV WEB SERVICES` context → `VPR GET PATIENT DATA` (XML)
- XML parsed and normalized to a JSON-like shape: `{ "items": [ ... ] }` consumed by existing transforms.

No fallback contexts are attempted (previous optional iteration removed). If your site uses a different label (e.g. `JLV WEB SERVICE` singular), set `VISTA_VPR_XML_CONTEXT` explicitly.

Unsupported domains are skipped in `fullchart`; most common domains (patient, med, lab, vital, document, image, procedure, visit, problem, allergy) are aggregated.

## Socket gateway: heartbeat, caching, and tuning

To improve responsiveness and reliability when using the VistA Broker socket, the refactor introduces three coordinated improvements in the socket gateway implementation:

- Heartbeat (keepalive and idle ping): the socket client can start a background heartbeat thread that periodically issues a lightweight RPC (`XUS GET USER INFO`) when the connection has been idle. This reduces full handshake reconnects (which are expensive and noticeable in the UI) and detects a dropped session quickly so the gateway can reconnect proactively.

- Short-term RPC caching for search/list calls: common, high-frequency RPCs used by the UI are cached for a short time to avoid repeated round-trips when the user repeatedly opens the patient list or types the same search prefix. Specifically:
  - `ORQPT DEFAULT PATIENT LIST` (default patients) is cached for a short TTL (default ~30s).
  - `ORWPT LAST5` and `ORWPT LIST ALL` (search) responses are cached keyed by RPC+parameters with a small LRU store (default size 24, TTL ~20s).

- Per-patient VPR domain cache: when fetching domain-level payloads (patient, med, lab, vital, problem, allergy) the gateway now optionally caches the parsed results in a small in-memory LRU with TTL. This cache is:
  - Per-site and per-patient keyed (so different site/session picks up different caches).
  - Size-limited and TTL-limited (defaults: per-domain TTL ~120s, cache size ~12 entries).
  - Disabled automatically for requests asking for full text or other parameters that indicate non-cacheable results (for example `text=1` or explicit filters that change the result set).

Eviction and hygiene
- When the socket client is reset (authentication error, connection abort), caches are flushed to avoid returning stale results after re-establishing a new session.
- When a user explicitly purges ephemeral session state (API: `POST /api/session/purge`), the server will attempt to clear the gateway's per-patient cache for that DFN so subsequent UI operations fetch fresh data.

Configuration knobs (environment variables)
- `VISTA_HEARTBEAT_INTERVAL` (seconds): heartbeat poll interval, default 60. Set to 0 to disable heartbeat.
- `VISTA_SOCKET_IDLE_SECONDS`: how long the socket may be idle before a pre-flight ping/reconnect is attempted, default 300.
- `VISTA_VPR_CACHE_TTL` (seconds): default TTL for per-domain VPR cache entries (default 120).
- `VISTA_VPR_CACHE_SIZE`: max entries in per-domain LRU (default 12).
- `VISTA_PATIENT_LIST_TTL`: TTL for cached `ORQPT DEFAULT PATIENT LIST` (default 30).
- `VISTA_PATIENT_SEARCH_TTL`: TTL for cached patient search responses (`ORWPT *`) (default 20).
- `VISTA_PATIENT_SEARCH_CACHE_SIZE`: size of patient search LRU (default 24).

Instrumentation & diagnostics
- The gateway logs heartbeat events and reconnect attempts under `[VistaRPC]` messages. If you still see many reconnects, consider raising heartbeat frequency or increasing socket idle threshold.
- For troubleshooting:
  - Watch for "socket connection aborted" messages which indicate the broker or network closed the connection.
  - Enable debug logging on the socket client for traces of handshake timing.

Front-end orchestration recommendations
- Debounce patient search inputs (200–400ms) and cancel in-flight list or full-chart fetches when the user selects a different patient to avoid wasted work.
- Re-use server-side cached search/list payloads where available instead of re-requesting immediately after a UI navigation.

Notes on security and correctness
- Cached results are kept in-memory on the server and scoped by site/session where possible. They are not persisted to disk. If you need cross-process sharing (multiple web workers), configure a shared cache (Redis) and adapt TTL/size accordingly.

Rollout guidance
- Start with heartbeat enabled and default TTLs. Monitor the logs for reconnects and UI latency. If your VistA site permits, increase `VISTA_HEARTBEAT_INTERVAL` for longer-lived sessions or lower it to keep sessions warmer when network is flaky.

This behavior is implemented in `app/gateways/vista_socket_gateway.py` and is invoked automatically when a socket-mode gateway is created via the factory. See that file for exact defaults and implementation details.

## Security considerations

- ACCESS/VERIFY stay server-side per session (Flask-Session).
- Cipher files should not be committed to source control and must be protected by OS ACLs.
- Prefer HTTPS in front of the app; use VA network policies for broker access.

## Extending gateways

See `app/gateways/data_gateway.py` for the interface and `app/gateways/factory.py` for runtime selection.
