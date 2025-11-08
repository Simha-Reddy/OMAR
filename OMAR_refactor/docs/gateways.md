# Gateways: vista-api-x (DEMO) and VistA Socket

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

## Security considerations

- ACCESS/VERIFY stay server-side per session (Flask-Session).
- Cipher files should not be committed to source control and must be protected by OS ACLs.
- Prefer HTTPS in front of the app; use VA network policies for broker access.

## Extending gateways

See `app/gateways/data_gateway.py` for the interface and `app/gateways/factory.py` for runtime selection.
