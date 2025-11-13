Frontend structure overview
===========================

This folder contains the client-side assets for the refactor UI: JavaScript modules, styles, images, and shared libraries.

Top-level layout
----------------
- `js/` — Application JavaScript (page bootstraps, workspace orchestrator, and feature modules)
- `styles/` — CSS (global theme + workspace layout)
- `images/` — Icons and images
- `lib/` — Shared client libraries and helpers (Tabulator, Luxon, dot phrases, etc.)
- `prompts/` — Prompt text used by UI flows (e.g., note scribe templates)

Workspace tabs (where they live)
--------------------------------
- Tabs are defined by modules under `js/workspace/modules/`.
  - Each file defines a tab module and registers itself on `window.WorkspaceModules[<Module Name>]` with a `render(container, options)` function and optional `refresh()`.
- The tab bar and tab content panes are managed by `js/workspace.js`, which dynamically loads modules and renders them into left/right workspace panes.
- Default tabs: Snapshot, Hey OMAR, Documents, Labs, Meds (left) and Note, After Visit Summary, To Do (right). The layout is persisted in `localStorage`.

Key workspace files
-------------------
- `js/workspace.js`
  - Orchestrates workspace loading for the selected patient.
  - Manages left/right tab bars, tab activation, persisted layout, floating tabs, and module loading via `<script>` injection from `js/workspace/modules/*`.
  - Exposes helpers (e.g., `WorkspaceTabs.resetLayout`, `refreshTabsByName`).
- `js/workspace_mobile.js`
  - Mobile-optimized workspace behaviors (reduced footprint, responsive tweaks).

Workspace modules (tabs)
------------------------
Located in `js/workspace/modules/`:
- `snapshot.js` — Patient overview panel (high-level summary and quick facts).
- `heyomar.js` — Hey OMAR conversational assistant tab; issues questions via Query API and renders answers/citations.
- `documents.js` — Documents explorer; initial and remaining loads controlled by the orchestrator for performance.
- `labs.js` — Labs list/visualization (uses LOINC mappings; may leverage Tabulator).
- `meds.js` — Medications tab (active/chronological views, quick filters).
- `note.js` — Note drafting tab (client-side UI that talks to `/scribe/*` endpoints).
- `after_visit_summary.js` — AVS generation tab.
- `todo.js` — To Do/Tasks pane (visit checklist, actions).

Other important JS files
------------------------
In `js/`:
- `app.js` — Global app bootstrapping and event wiring common to multi-page flows.
- `workspace.js` — See above; the workspace orchestrator and tab system.
- `workspace_mobile.js` — Mobile workspace adjustments.
- `api.js` — Lightweight REST helpers and common fetch wrappers for API calls.
- `csrf_fetch.js` — Adds CSRF headers/cookies to fetch requests (double-submit protection).
- `SessionManager.js` — Polls/reads ephemeral state (e.g., scribe transcript) for the current user/patient.
- `patient_switch.js` — Handles patient context switching, broadcasts events, and resets UI state.
- `selectpatient.js` — Patient search/select flow UI.
- `patient.js` — Patient page-specific helpers (demographics loading, formatting utilities).
- `explore.js` — Explore page interactions (search, early RAG hooks if enabled).
- `hey_quick.js` — Lightweight Hey OMAR quick ask (popup/inline usage).
- `note.js` — Legacy/standalone note UI interactions (distinct from workspace Note tab’s module file).
- `scribe.js` — Scribe UI for drafting notes from transcript; calls `/scribe/create_note` and `/scribe/chat_feedback`.
- `scribe_provider_note_recorder.js` — Wires the browser audio recorder to `/api/scribe/*` endpoints.
- `scribe_runtime.js` — Scribe runtime state/orchestration helpers shared across scribe UI components.
- `archive.js` — Archive view interactions (load/display previous chats/notes/answers).
- `popups.js` — Generic popup utilities (modal dialogs, toast notifications).
- `omar_history_popup.js` — History sidebar/popup for prior OMAR interactions.
- `settings.js` — Settings page interactions and persistence.
- `ui.js` — Generic UI helpers (DOM utilities, formatting, small components).
- `debug_dfn.js` — Developer helper to set/inspect current patient DFN from the client.
- `icon.ico` — App icon (served under static).

Shared libraries (`lib/`)
--------------------------
- `dot_phrases.js` — Client-side dot-phrase expansion utilities (e.g., .labs, .orders).
- `documentService.js` — Thin client-side document fetch/cache helper for the Documents tab.
- `demographics_overlay.js` — Overlay and formatting helpers for patient demographics.
- `LOINC_table.csv` — LOINC code table used by Labs and related components.
- `luxon.min.js` — Date/time library used for formatting and calculations.
- `marked.min.js` — Markdown rendering for note/answer content.
- `tabulator*.js/css` — Tabulator grid library used by data-heavy tables (labs, meds, documents).
- See `lib/README.md` for details specific to libraries.

How modules register
-------------------
Each tab module script should register itself on a global registry:

```javascript
window.WorkspaceModules = window.WorkspaceModules || {};
window.WorkspaceModules['Module Name'] = {
  // Required: render content into the provided container
  render: async function(container, options) { /* ... */ },
  // Optional: refresh soft/hard behaviors for DFN changes or tab activation
  refresh: function() { /* ... */ },
  refreshSoft: function() { /* ... */ },
  // Optional: clean up inflight operations on patient switch
  destroy: function() { /* ... */ },
  // Optional: advise orchestrator to preserve DOM on refresh
  preserveOnRefresh: true
};
```

Adding a new tab
----------------
1) Create `js/workspace/modules/<your_tab>.js` and register your module as above.
2) Ensure the module key matches the visible tab name (e.g., `'Orders'`).
3) Update the `moduleConfig` map in `js/workspace.js` to point the tab name to your script filename.
4) Optionally add to default layout by editing the `initialTabs` list in `js/workspace.js`.

Events and patient context
--------------------------
- Most modules should read the current DFN from `sessionStorage.CURRENT_PATIENT_DFN` via `workspace.js` helpers.
- The orchestrator dispatches and listens for events such as `patient:loaded`, `workspace:layoutChanged`, `documents:initial-indexed`.
- On patient switch, the orchestrator blanks old tab content and triggers module re-renders.

Security notes
--------------
- All POST/PUT/PATCH/DELETE requests must include the CSRF header and cookie. Use `csrf_fetch.js` helpers or ensure the header is set.
- Avoid embedding PHI in client storage beyond transient session usage; prefer server ephemeral state where possible.
