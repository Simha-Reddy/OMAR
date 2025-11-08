Frontend structure overview
===========================

Last updated: 2025-11-07

Migrated from `static/README.md` to centralize documentation.

Structure
---------
- `static/js/` — Application JavaScript modules
- `static/styles/` — CSS
- `static/images/` — Assets
- `static/lib/` — Shared client libraries (see `docs/frontend_libraries.md`)
- `static/prompts/` — Prompt text assets

Workspace
---------
- Tabs live in `static/js/workspace/modules/` and register on `window.WorkspaceModules` with `render()` and optional `refresh()` functions.
- Orchestrated by `static/js/workspace.js` and `static/js/workspace_mobile.js`.

Important JS files
------------------
- `static/js/app.js` — Global bootstrapping and wiring
- `static/js/workspace.js` — Tab system and layout persistence
- `static/js/api.js` — REST helpers
- `static/js/csrf_fetch.js` — CSRF protection helpers
- `static/js/SessionManager.js` — Ephemeral state polling
- `static/js/patient_switch.js`, `static/js/selectpatient.js` — Patient context and selection flows
- Modules: `snapshot.js`, `heyomar.js`, `documents.js`, `labs.js`, `meds.js`, `note.js`, `after_visit_summary.js`, `todo.js`

Security notes
--------------
- Include CSRF header + cookie on all mutating requests.
- Avoid persisting PHI in client storage beyond transient usage; prefer server ephemeral state.
