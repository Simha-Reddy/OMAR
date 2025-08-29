# SimpleScribe Agent Tool Catalog (v1)

Allowed tools are read-only and scoped to a single patient. All tools must respect plan budgets (rows/bytes/timeout). Unknown parameters are ignored. Passing unexpected types fails validation.

Global parameter fields (where applicable):
- patient_id: string (required)
- date_range: { start: ISO 8601, end: ISO 8601 } (optional)
- limit: integer, 1–1000 (optional, server may clamp lower)

Notes:
- Codes lists are allow-listed subsets per tool (e.g., LOINC for labs). Max 50 codes per request.
- All responses include source provenance and timestamps.

## get_labs(params)
Fetch lab results. Units and reference ranges are required.

Params:
- patient_id: string
- date_range?: { start: string, end: string }
- codes?: string[] (LOINC)
- limit?: number

Response items (LabResult):
- { code, display, value, unit, referenceRange?, effectiveDateTime, source:{system, updated} }

Example request:
```json
{"tool":"get_labs","params":{"patient_id":"123","codes":["4548-4","17856-6"],"date_range":{"start":"2023-01-01T00:00:00Z","end":"2025-12-31T23:59:59Z"},"limit":200}}
```

## get_vitals(params)
Fetch vital signs (e.g., Weight, BP, BMI).

Params:
- patient_id: string
- date_range?: { start, end }
- types?: (optional) ["Weight","BP","BMI"]
- limit?: number

Response items (Vital):
- { type, value, unit, effectiveDateTime, source:{system, updated} }

Example request:
```json
{"tool":"get_vitals","params":{"patient_id":"123","date_range":{"start":"2024-01-01T00:00:00Z","end":"2025-12-31T23:59:59Z"},"limit":365}}
```

## get_meds(params)
Fetch medications.

Params:
- patient_id: string
- status?: "active"|"stopped"
- date_range?: { start, end } (applies to startDate)
- limit?: number

Response items (Medication):
- { name, dose, route, frequency, startDate?, status, source:{system, updated} }

Example request:
```json
{"tool":"get_meds","params":{"patient_id":"123","status":"active","limit":200}}
```

## get_problems(params)
Fetch problem list entries.

Params:
- patient_id: string
- status?: "active"|"resolved"
- limit?: number

Response items (Problem):
- { text, status, onset?, source:{system, updated} }

Example request:
```json
{"tool":"get_problems","params":{"patient_id":"123","status":"active","limit":100}}
```

## get_notes(params)
Fetch note metadata only (no full text). May include approved summary fields only.

Params:
- patient_id: string
- date_range?: { start, end }
- limit?: number

Response items (NoteMeta):
- { date, title, service?, snippet?, summary?, source:{system, updated} }

Example request:
```json
{"tool":"get_notes","params":{"patient_id":"123","date_range":{"start":"2024-06-01T00:00:00Z","end":"2025-08-23T23:59:59Z"},"limit":200}}
```

## get_notes_search_results(params)
Retrieve relevant note excerpts (chunks) for a query using the patient RAG index. Requires notes to be indexed via the Explore workflow.

Params:
- patient_id: string
- query: string (required)
- top_k?: integer (1–20, default 8; smaller is better for budgets)
- doc_ids?: string[] (optional filter to restrict results to specific note IDs)

Response items (NoteChunk):
- { note_id, chunk_id, text, rank, score, source:{system:"rag", updated} }

Example request:
```json
{"tool":"get_notes_search_results","params":{"patient_id":"123","query":"ACE inhibitor intolerance","top_k":8}}
```

---

Budget enforcement:
- Plans must include budget: { rows, bytes, timeout_ms }.
- Server enforces the stricter of tool defaults vs. plan.
- Datasets may be truncated to meet budgets; executor returns truncation flags.
