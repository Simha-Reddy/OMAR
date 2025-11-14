Backend application structure
=============================

This package contains the Flask application code for OMAR. It is organized into layered concerns: request routing (blueprints), external system gateways, RAG / query models, scribe (audio + note drafting), AI tooling utilities, and domain services.

High-level layout
-----------------
- `__init__.py` — Application factory (`create_app()`); config, session/Redis wiring, CSRF middleware, security headers, blueprint registration.
- `blueprints/` — Lightweight HTTP endpoint definitions for non-query features (patient, search, session state, archives, CPRS sync, general UI).
- `query/` — Query model registry + providers implementing retrieval augmented generation (RAG) answering flow (`default` model, rewriting, fusion, prompt assembly).
- `scribe/` — Audio ingestion + transcription (`scribe_api`), note drafting/chat (`note_api`), transcription providers, prompts, docs.
- `gateways/` — Adapters to external systems (e.g., VistA RPC / API wrappers, patient data access) returning normalized data structures.
- `services/` — Server-side utility logic not tied to a single blueprint (e.g., indexing, caching helpers, ranking utilities, planner logic, embeddings store).
- `ai_tools/` — Shared AI integration helpers (LLM clients, embedding functions, prompt templates, token counting logic).

Request flow overview
---------------------
1. Incoming HTTP request hits a registered blueprint route.
2. Blueprint parses inputs (JSON or query params), performs auth / patient guard checks (where implemented).
3. Delegates to a gateway/service for data retrieval or to a query model provider for RAG answering.
4. Provider orchestrates retrieval (BM25 + embeddings, multi-query rewrite, RRF fusion), constructs a structured prompt (demographics, problems, meds, structured sections), calls LLM, returns answer + citations.
5. Response is serialized to JSON with security headers and CSRF cookie set by global middleware.

Blueprints
----------
Examples (exact filenames may vary):
- `general.py` — Health check, landing page or static helper endpoints.
- `patient.py` — Patient-specific endpoints (`/api/patient/<dfn>/quick/demographics`, etc.).
- `patient_search.py` — Search endpoints for selecting a patient.
- `archive_api.py` — Archive listing and retrieval for prior answers / notes.
- `session_api.py` — Ephemeral session state CRUD (transcript linking, visit IDs).
- `query_api.py` — Query interface: POST /api/query/ask for Hey OMAR or Explore style questions (passes structured sections, flags).
- `cprs_api.py` — CPRS synchronization or placeholder endpoints (if implemented).
- `scribe_api` (moved) — Lives now under `scribe/blueprints/scribe_api.py` for audio ingestion at `/api/scribe/*`.
- `note_api` — Lives under `scribe/blueprints/note_api.py` at `/scribe/*` for note drafting.

Query subsystem (`query/`)
--------------------------
Core pieces:
- `blueprints/query_api.py` — Entry point for incoming ask requests: resolves active model from registry, forwards payload.
- `query_models/default/provider.py` — Default model implementation (multi-query rewrite, hybrid retrieval, RRF fusion, prompt assembly, LLM call, citation mapping).
- Retrieval helpers (e.g. `services/rag.py`) — BM25 / embedding hybrid search, chunk windowing, scoring boosts.
- Registry — Maps model names to provider classes for extensibility.

Retrieval algorithm (default provider):
1. Generate rewrites (LLM) for the original user query (3–4 variants).
2. Retrieve top chunks per rewrite (hybrid BM25 + vector if available).
3. Apply Reciprocal Rank Fusion (RRF) to aggregate results.
4. Apply heuristic boosts (title tags, recency, note type).
5. Assemble preface (demographics, problems list, active meds) + structured sections from client.
6. LLM answer with citations and visible chunk excerpts.

Scribe subsystem (`scribe/`)
----------------------------
- `blueprints/scribe_api.py` — Session management and audio streaming; transcripts persisted to Redis + ephemeral state mirror.
- `blueprints/note_api.py` — Draft creation + chat refinement; system preface loaded from `prompts/scribe_system.md`; Azure OpenAI or dev echo fallback.
- `providers.py` — Transcription providers (DevEcho, Azure Speech) selected via env vars.
- `README.md` — Detailed architecture, endpoints, env, extension guidance.

Gateways
--------
Encapsulate communication with external systems (e.g., VistA, FHIR, databases). Responsibilities:
- Maintain a clean boundary: translate external formats into internal Python dicts/data classes.
- Provide caching or batching where appropriate.
- Avoid leaking transport/client details into blueprint or provider logic.

Services
--------
Cross-cutting logic:
- Indexing workflow (select notes to embed: recent 100 progress notes, all discharge summaries, consult notes, radiology).
- Embeddings store (cache vectors, compute missing ones asynchronously or on-demand).
- Ranking heuristics, token counting, prompt sanitation.
- Planner utilities (if/when deep second-pass implemented).

AI tools (`ai_tools/`)
---------------------
- LLM client wrappers (Azure OpenAI, local dev mocks) with standardized interface (e.g., `chat(messages, temperature)`).
- Embedding functions with batching, retry/backoff, and cache key derivation.
- Prompt fragments (system prefaces, section templates) consolidated for reuse.

Configuration & environment
--------------------------
Key environment variables:
- Flask / security: `FLASK_SECRET_KEY`, `SESSION_COOKIE_SECURE`, `EPHEMERAL_STATE_TTL`.
- Redis: `REDIS_HOST`, `REDIS_PORT`, `USE_FAKEREDIS`.
- Azure OpenAI: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_DEPLOYMENT_NAME`, `AZURE_API_VERSION`.
- Speech: `SCRIBE_TRANSCRIBE_PROVIDER`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `AZURE_SPEECH_ENDPOINT`, `SCRIBE_LANG`.
- Feature flags (from app factory): `USE_VAX_GATEWAY`, `EPHEMERAL_SERVER_STATE`, `AUTO_ARCHIVE_DEFAULT`.

Security middleware
-------------------
Implemented in `create_app()`:
- Per-response cache-control + security headers (CSP, X-Frame-Options, etc.).
- CSRF double-submit cookie regeneration and validation for mutating requests.
- Colored log traces for environment verification.

Ephemeral state
---------------
Redis-backed per (user, patient) state storing evolving transcript and visit metadata. Used by scribe and potentially other real-time features. TTL configurable via env.

Extending the backend
---------------------
1. Add a new blueprint: create file under `blueprints/`, import/register in `create_app()`.
2. Introduce a new query model: implement provider under `query/query_models/<name>/provider.py` and register in the model registry.
3. Add a gateway: create module under `gateways/` with clear interface and docstring contract (inputs/outputs, error modes).
4. Expand retrieval heuristics: adjust `services/rag.py` or provider scoring logic; ensure tests updated.
5. Schedule background embedding: add a service function that queues notes for embedding and integrate with provider pre-retrieval path.

Error handling strategy
-----------------------
- Blueprint level: validate input early, return JSON `{ error: <message> }` with appropriate status codes (400, 404, 409, 500).
- Provider level: catch LLM/transcription failures, degrade gracefully (empty rewrite list falls back to original query; failed transcription chunk yields no delta).
- Gateway level: wrap external exceptions, surface minimal error context (avoid leaking internal stack traces).

Testing guidelines (suggested)
------------------------------
- Unit test providers with mocked gateways + LLM client to exercise rewrite + fusion logic deterministically.
- Integration test query endpoint with a fake embedding store (pre-populated vectors) to assert retrieval ordering.
- Scribe tests patch `get_transcription_provider()` to return fixed text.
- Gateway tests simulate external responses (JSON fixtures).

Future enhancement hooks
------------------------
- Feature-flag deep second-pass note expansion (planner-based full note retrieval + re-ask) integrated into provider.
- Embedding prefetch scheduler (background job scanning latest notes and maintaining vector freshness).
- Multi-tenant isolation of Redis keys and session state.
- Observability: structured logs + metrics for rewrite counts, retrieval latency, LLM token usage.

Glossary (quick reference)
--------------------------
- DFN: Patient identifier (internal numeric/string key).
- RRF: Reciprocal Rank Fusion – merges ranked lists from multiple query rewrites.
- Chunk: Document excerpt unit used for retrieval scoring and prompt citation.
- Ephemeral state: Short-lived Redis entry holding real-time per-user/patient transcript and metadata.

Maintenance notes
-----------------
- Keep blueprint layer thin; heavy logic belongs in services / gateways.
- Avoid circular imports by keeping `create_app()` centralized and gateways decoupled from blueprints.
- Prefer dependency injection (pass gateway/provider) for testability rather than importing globals inside functions.

End of overview.
