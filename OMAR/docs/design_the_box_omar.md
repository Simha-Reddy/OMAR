# OMAR – Design the Box

## Tagline

AI-connected clinical assistant that reimagines the VA clinician workspace, combining ambient scribing, natural language chart querying, and customizable patient data views.

## URL
- https://vhacdwdwhocc15.vha.med.va.gov/tfs/DHO_AIET/OMAR/

## Product Road Map

- **Near-term (0–6 weeks)**
  - Deploy OMAR to VA Azure test environment for early clinician test users.
  - Harden privacy and logging; instrument for feedback capture and bug reporting.
  - Rapid-cycle UI, performance, and reliability improvements based on test-user feedback. Focus on any potential patient safety risks (hallucinations, wrong patient, etc).
- **Short-term (6–12 weeks)**
  - Add ability to save unsigned draft notes into CPRS, connected to encounter.
  - Extend VistA data access beyond the local instance to remote VistA sites.
  - Refine note prompts, document search, and "Hey OMAR" answers using real-world usage patterns.
- **Medium-term (3-4 months)**
  - Develop new tabs such as Smart Problem List, longitudinal Timeline, and Medication Reconciliation to surface complex chart patterns at a glance.
  - Add workflows to save After Visit Summaries directly into the chart.
  - Support "To Do" items that write Task Tickler clinical reminders in CPRS.
  - Expand Hey OMAR with alternative retrieval/query engines (e.g., knowledge-graph-based chart reasoning) while continuing incremental improvements to the current RAG pipeline.
- **Longer-term (6+ months)**
  - Add support for multi-patient workflows based on a user’s default patient list (e.g., clinic huddle sheets and panel review views).
  - Allow for view alert management
  - Integrate MyHealtheVet secure messaging.
- **When permitted (High Priority)**
  - Incorporate EHRM-G / "outside records" data into OMAR once access is permitted, allowing for powerful query/summarization of community records, and improving integration of VA-funded Community Care.



## Current Features

- Ambient note scribing that records clinician–patient encounters (with consent), performs speech-to-text, and drafts structured notes using configurable prompts.
- "Hey OMAR" natural-language query of the chart with retrieval-augmented answers and clickable citations back to source TIU notes and documents.
- Patient snapshot views for problems, medications, vitals, labs, and documents, optimized for fast review before and during visits.
- Document search and indexed note excerpts with simple filters, making it easier to rediscover key findings and prior plans.
- Patient instruction drafting to generate clear, editable After Visit Summary language suitable for patient-facing handouts.
- Modular, tab-based workspace that can add new views (e.g., future Smart Problem List, Timeline, Med Rec, task panels) without redesigning the whole app.
- Pluggable query model architecture so alternate LLMs, retrieval strategies, or knowledge-graph engines can be A/B tested behind a stable UI.
- Built-in privacy and security measures: CSRF protection, conservative caching headers, explicit PHI retention controls, and integration only with VA back-end services.

## Benefits

### For Clinicians

- Reduces documentation burden by drafting notes and patient instructions, saving clicks and time in CPRS-heavy workflows.
- Speeds up chart review through fast Q&A (e.g., _"What has been done for heart failure so far?"_) with transparent citations.
- More time focused on the Veteran
- Keeps clinicians in control: OMAR assists with summarization and retrieval but is not allowed to make any clinical recommendations.

### For VA as an Organization

- Provides a VA-owned, extensible platform for experimenting with AI-assisted workflows on top of legacy and evolving EHR infrastructure.
- Encourages reuse of a common workspace pattern and query abstraction instead of duplicative local tools.
- Supports safety and compliance through clear boundaries: VA-hosted services, clearly defined minimal and auditable PHI, avoids clinical recommendations.
- Potential to improve clinician satisfaction, reduce burnout, and enhance documentation quality, with downstream benefits for care quality and coding accuracy.

## Client-Side

- Browser-based workspace that runs alongside CPRS, offering tabbed views (Hey OMAR, Snapshot, Note, Labs etc.).
- JavaScript modules for each workspace tab (e.g., Hey OMAR query panel, note scribe controls, patient snapshot) loaded dynamically from static assets.
- In-browser audio capture for ambient scribing, using the microphone to stream audio chunks to the server for transcription.
- Rich interactive features such as clickable citations that open note excerpts, patient search and switching, and configurable prompts and layouts.
- CSRF-aware fetch utilities and careful handling of PHI in the browser (e.g., no-store cache controls, minimal data in logs).

## Server-Side

- Flask-based Python backend coordinating patient context, data gateways, scribe pipelines, query models, and session state.
- VistA data gateways abstracted behind a unified interface: DEMO HTTP (vista-api-x) mode and Broker Socket (JLV XML/VPR) mode, with normalized transforms feeding the UI and query subsystem.
- Query subsystem using a document index and hybrid retrieval (embeddings + BM25) to retrieve and score chart excerpts for Hey OMAR.
- Scribe subsystem handling audio ingestion, speech-to-text, and LLM-driven note drafting, with drafts stored only in server-side session space unless explicitly archived.
- Configurable feature flags and environment variables for privacy, session lifetime, archival behavior, and model/gateway selection.
- Blueprint-based API design for patient endpoints (`/api/patient/...`), query endpoints (`/api/query/...`), scribe endpoints (`/api/scribe/...`), user settings, archives, and future CPRS integration endpoints (e.g., saving drafts, reminders).

## Integrations

- VA Azure OpenAI (or equivalent VA-hosted LLM endpoints) for note drafting, chart summarization, and Hey OMAR answers, accessed only via approved internal endpoints.
- VA Azure speech-to-text provider for converting recorded audio into transcripts, used by the scribe subsystem. Can be swapped out for local speech-to-text models.
- VistA data access via vista-api-x HTTP gateway or Broker Socket gateway, designed to support both demo and production-like data flows now, and potential shift in future fully to HTTP approach.
- Future integration plans: SMART on FHIR endpoints, EHRM-G/"outside records" sources, and secure messaging systems, once policy and technical access are available.