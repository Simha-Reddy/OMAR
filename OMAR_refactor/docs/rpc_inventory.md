RPC Inventory (Socket and HTTP VistA Calls)
==========================================

Last updated: 2025-11-07

This document lists every VistA RPC invoked directly or via vista-api-x within OMAR_refactor.
Top list: RPC name | Context(s) | Purpose.
Below: detailed sections with parameters, response parsing, and usage sites.

Summary table
-------------

<!-- RPC_TABLE_START -->
| RPC Name                     | Context(s)            | Purpose                                                     |
|------------------------------|-----------------------|-------------------------------------------------------------|
| DG SENSITIVE RECORD ACCESS   | OR CPRS GUI CHART     | Sensitive record access check; returns status/message       |
| ORQPT DEFAULT PATIENT LIST   | OR CPRS GUI CHART     | Default patient list for user                               |
| ORWU USERINFO                | OR CPRS GUI CHART     | Minimal user DUZ/name/division info                         |
| ORWPT LAST5                  | OR CPRS GUI CHART     | Patient lookup by LAST5 token                               |
| ORWPT LIST ALL               | OR CPRS GUI CHART     | Patient name prefix search with paging                      |
| ORWPT TOP                    | OR CPRS GUI CHART     | Currently selected CPRS patient (sync)                      |
| VPR GET PATIENT DATA         | JLV WEB SERVICES      | Fetch patient domain (XML variant; socket mode)             |
| VPR GET PATIENT DATA JSON    | LHS RPC CONTEXT       | Fetch patient domain or full chart (JSON; DEMO HTTP mode)   |
<!-- RPC_TABLE_END -->

(Keep this table alphabetically sorted by RPC Name. Do not edit the rows manually; run the auto-sync script below.)

Auto-sync this table
--------------------

This repository includes a helper script that scans the codebase for RPC usages and regenerates the summary table above between the markers RPC_TABLE_START/END.

How to run (Windows PowerShell):

1) Preferred: use the embedded Python in `OMAR_refactor/python/`.
	- From the repo root:
	  - `& "OMAR_refactor/python/python.exe" OMAR_refactor/scripts/update_rpc_inventory.py`

2) Or use your active Python:
	- `python OMAR_refactor/scripts/update_rpc_inventory.py`

What it does:
- Finds `gateway.call_rpc(context=..., rpc=...)` calls and `call_in_context(..., 'RPC NAME', ...)` patterns
- Detects `VPR GET PATIENT DATA JSON` and `VPR GET PATIENT DATA` usages in gateways
- Merges with any existing Purpose text in the current table so custom descriptions are preserved
- Writes the updated, alphabetically-sorted table back into this document

Notes:
- Purpose text for newly detected RPCs defaults to `-` until you edit it here; the script will preserve your changes next runs.
- Contexts may be literals (e.g., `OR CPRS GUI CHART`) or inferred (e.g., `JLV WEB SERVICES` for socket VPR XML).

Detailed sections
-----------------

### VPR GET PATIENT DATA JSON
- Context: `LHS RPC CONTEXT` (configurable via `VISTA_API_RPC_CONTEXT` env; DEMO HTTP mode only)
- Gateway: `VistaApiXGateway.get_vpr_domain()` / `get_vpr_fullchart()`
- Parameters: sent as a single named array `{ "patientId": <DFN>, "domain": <domain?>, ...filters }`
- Filters: domain-specific (e.g., `start`, `stop`, `max`, `id`, `uid`, `text`) passed through when provided.
- Response: JSON object containing `data.items` list (vista-api-x normalized). Consumed by transforms under `app/services/transforms.py`.
- Usage sites: multiple quick endpoints (labs, meds, vitals, documents, notes, etc.) via `PatientService` when DEMO mode active.

### VPR GET PATIENT DATA
- Context: `JLV WEB SERVICES` (socket mode). Override via `VISTA_VPR_XML_CONTEXT` if site differs.
- Gateway: `VistaSocketGateway.get_vpr_domain()` (calls `_client.call_in_context(...)` with namedArray)
- Parameters: same named array as JSON variant: `{ patientId: DFN, domain: <domain?>, ...filters }`
- Response: raw XML; parsed by `xmltodict` and normalized to `{ "items": [ ... ] }` in `_normalize_vpr_xml_to_items()`.
- Usage sites: all socket-mode patient domain fetches and `get_vpr_fullchart()` aggregation.

### ORQPT DEFAULT PATIENT LIST
- Context: `OR CPRS GUI CHART`
- Endpoint: `/vista_default_patient_list` (`patient_search.py`)
- Parameters: none
- Response: caret-delimited lines: `<DFN>^<NAME>^<CLINIC?>^<DATE?>`; parsed into `patients[]` list.
- Additional calls: Immediately followed by `ORWU USERINFO` in same context to enrich response with user info.

### ORWU USERINFO
- Context: `OR CPRS GUI CHART`
- Endpoint: `/vista_default_patient_list` (secondary call inside handler)
- Parameters: none
- Response: first caret-delimited line, DUZ^NAME^...^DIVISION; division heuristically parsed from last caret segment / semicolon.

### ORWPT LAST5
- Context: `OR CPRS GUI CHART`
- Endpoint: `/vista_patient_search` (branch for LAST5 queries: 1 letter + 4 digits)
- Parameters: single string parameter: LAST5 token
- Response: caret-delimited lines `<DFN>^<NAME>^...`; parsed to matches list.

### ORWPT LIST ALL
- Context: `OR CPRS GUI CHART`
- Endpoint: `/vista_patient_search` (name prefix search)
- Parameters: two string params: FROM cursor (`<PREFIX_MODIFIED>~`) and page length indicator (`"1"`)
- Name transformation: last character decremented (A→@, B→A, etc.) then appended `~` to form inclusive prefix range.
- Response: caret-delimited lines; filtered client-side so `NAME` starts with original prefix; paging via nextCursor (last name of page).

### ORWPT TOP
- Context: `OR CPRS GUI CHART`
- Endpoint: `/sync` in `cprs_api.py`
- Parameters: none
- Response: caret-delimited record; first two segments used for `dfn` and `name`.
- Purpose: sync current CPRS-selected patient to OMAR workspace.

### DG SENSITIVE RECORD ACCESS
- Context: `OR CPRS GUI CHART`
- Endpoint: `/<dfn>/sensitive` in `patient.py`
- Parameters: single string DFN
- Response: lines; first line often numeric status code (`0` = not sensitive). Remaining lines may include warning text. Heuristic fallback sets `allowed=False` if warning/sensitive keywords present.
- Output mapping: `{ allowed: !is_sensitive, message: <warning text>, raw: <full response> }`.

Parsing & helpers
-----------------
- `patient_search.py` and `cprs_api.py` use `_unwrap_vax_raw()` to unwrap potential `{ "payload": "..." }` JSON envelopes from vista-api-x HTTP responses.
- Socket gateway returns plain caret/newline text; HTTP gateway may return JSON string or payload wrappers.

Adding a new RPC
----------------
1. Implement call via `gateway.call_rpc(context=..., rpc=<NAME>, parameters=[...])` in a blueprint or service.
2. Parse response (caret-delimited vs JSON vs XML) as needed.
3. Append RPC to the plain summary list (keep alphabetical order).
4. Add a detailed section with context, parameters, response shape, and usage.
5. If domain-specific and patient-scoped, consider whether a quick transform should be added for UI consumption.

Maintenance notes
-----------------
- Keep contexts minimal: prefer `OR CPRS GUI CHART` unless a specialty context is required.
- For socket mode, avoid frequent context switching (batch related RPCs under the same context).
- Revisit sensitive record logic for any additional status codes beyond numeric first line.

Proposed future additions (placeholder)
--------------------------------------
- TIU GET RECORD TEXT (per-note text retrieval fallback) — if needed for sites where VPR domain `document` lacks full text.
- ORQQPL LIST (Problems listing alternative) — integrate into problems quick if differences arise.

End of inventory.
