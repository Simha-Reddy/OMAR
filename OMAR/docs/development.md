# OMAR Refactor Development Notes

_Last updated: 2025-11-14_

## Environment Summary
- Python 3.11 runtime with dependencies pinned in `OMAR/requirements.txt`.
- Flask application entry point lives in `src/omar/__init__.py` (`create_app`).
- Runtime artifacts (archives and config) are expected under `runtime/`.
- Secrets are injected via environment variables – no plaintext secrets are committed.

## Local Setup
1. Create and activate a virtual environment (optional but recommended).
2. Install dependencies:
   ```bash
   python -m pip install -r OMAR/requirements.txt
   ```
3. Copy `deploy/.env.example` to `deploy/.env` (or export variables manually) for docker-compose driven runs.
4. When running against a VistA socket, provide either:
   - `VISTARPC_CIPHER_FILE` pointing to a cipher table file, or
   - inline `VISTARPC_CIPHER` content.

The Flask factory reads `OMAR_ENV_FILE` first; if unset or missing it falls back to `.env` in the working directory.

## Docker & Compose
- `OMAR/Dockerfile` builds a minimal gunicorn-backed image. It now provisions `runtime/config/` inside the image and sets `OMAR_ENV_FILE=/app/runtime/config/.env`. Mount a secret at that path (or override the variable) when running in Kubernetes/App Service.
- Local `docker-compose` (`deploy/docker-compose.yml`) keeps Redis as the session backend and reads environment values from `deploy/.env`.

## Azure DevOps Pipeline
We ship an opinionated pipeline at `deploy/azure-pipelines-omar.yml` that:
1. Checks out the repo and pins Python 3.11.
2. Downloads the `.env` and `cipher.txt` secure files using [`DownloadSecureFile@1`](https://learn.microsoft.com/azure/devops/pipelines/library/secure-files?view=azure-devops).
3. Installs Python dependencies and runs `pytest` with `OMAR_ENV_FILE` / `VISTARPC_CIPHER_FILE` pointing to the downloaded secrets.
4. Copies the secure artifacts into `OMAR/runtime/config/` so test runs mimic production layout.
5. Builds the Docker image (no push by default).
6. Removes the secure files — both the originals and staged copies — at job completion.

**Pipeline prerequisites**
- Upload your `.env` and `cipher.txt` into the Azure DevOps Library → Secure files. The filenames must match the `secureFile` values defined in `azure-pipelines-omar.yml` (default: `.env` and `cipher.txt`).
- Grant the pipeline access to each file and, if desired, lock it to this pipeline.
- Update the `secureFile` values in `azure-pipelines-omar.yml` if you choose different names.
- The `Stage secure files for tests` step mirrors [Microsoft’s guidance](https://learn.microsoft.com/azure/devops/pipelines/library/secure-files?view=azure-devops) by copying downloaded assets into the workspace, but it keeps everything inside the build agent (no `sudo` required).
- If you want to push the image, add a Docker registry service connection and extend the pipeline with a `Docker@2` `buildAndPush` step.

## Current Feature State
- Socket orders fetch path now enforces the `TYPE="orders"` guard and surfaces optional raw payloads.
- Order transforms categorise scheduling/consult entries based on `type_detail` fallbacks.
- UI additions: quick orders button, ad-hoc endpoint fetcher, dot-phrase `.orders/<category>` parity with backend filters.
- Runtime configuration defaults to Redis-backed sessions with FakeRedis available for local dev (`USE_FAKEREDIS=1`).

Use this document as the living checklist for onboarding and CI/CD expectations. Update it alongside architectural or pipeline changes to avoid drift.
