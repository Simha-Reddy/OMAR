# OMAR_refactor Deployment Plan and Docker Stack

This document captures the deployment approach for running OMAR_refactor on a multi-user server and details the Docker-based implementation that accompanies it.

## 1. Deployment goals

- Serve the Flask application behind a production-grade WSGI server (Gunicorn) with worker concurrency suitable for multiple users.
- Persist user session state outside the container (Redis) and make workspace artifacts durable via volumes.
- Provide reproducible environment configuration via `.env` files and documented runtime switches.
- Supply container health checks, logging, and baseline observability hooks.
- Enable local parity with a `docker-compose` stack that mirrors production dependencies.

## 2. Container architecture

| Component | Image | Responsibility |
|-----------|-------|----------------|
| `app`     | Built from project `Dockerfile` | Runs OMAR via Gunicorn, serves static assets, talks to Redis. |
| `redis`   | `redis:7-alpine` | Backing session store for Flask-Session and ephemeral caches. |

Key characteristics:

- Python 3.11 slim base, pip-installed dependencies from the pinned `requirements.txt`.
- Non-root `omar` user in the container for better isolation.
- Gunicorn (gthread workers by default) as the entrypoint; configurable via environment variables.
- `/healthz` endpoint exposed for Kubernetes/compose health checks.
- A single `runtime/` directory collects archives and optional examples. It is volume-mounted so PHI never bakes into the image.

## 3. Environment configuration

Environment variables live in `deploy/.env` (seeded from `deploy/.env.example`). Highlights:

- **Secrets & sessions**: `FLASK_SECRET_KEY`, `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`, `SESSION_LIFETIME_SECONDS`.
- **Redis**: `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`, `USE_FAKEREDIS=0` for production-grade storage.
- **Runtime directory**: `OMAR_RUNTIME_ROOT` defaults to `/app/runtime` in Docker and `<repo>/runtime` for local runs. Override if you mount an external path.
- **Gateway defaults**: `DEFAULT_STATION`, `DEFAULT_DUZ`, `VISTA_DEFAULT_CONTEXT`, `VISTA_VPR_CONTEXT`.
- **AI providers**: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_DEPLOYMENT_NAME`, `AZURE_API_VERSION`, `AZURE_SPEECH_*` keys.
- **Gunicorn tuning**: `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`, `GUNICORN_LOGLEVEL`.
- **Public port**: `OMAR_HTTP_PORT` controls host port mapping in compose.

Keep production secrets outside of source control (e.g., managed via secret stores or deployment platform variables).

## 4. Build and run workflow

1. Copy the example environment file:

   ```bash
   cd deploy
   cp .env.example .env
   # Edit .env with production values
   ```

2. Build and start the Docker stack:

   ```bash
   docker compose up --build -d
   ```

   The application becomes available on `http://localhost:8080` by default. Modify `OMAR_HTTP_PORT` to expose a different host port.

3. Tail logs or check service health:

   ```bash
   docker compose logs -f app
   docker compose ps
   docker compose exec app curl -fsS http://localhost:5050/healthz
   ```

4. Stop the stack when finished:

   ```bash
   docker compose down
   ```

### Upgrading / redeploying

```bash
docker compose pull
docker compose build
docker compose up -d
```

Docker volumes (`omar_runtime`, `omar_redis`) preserve critical data across redeployments. Remove them with `docker compose down -v` only when acceptable.

## 5. Production checklist

- **TLS termination**: Place the container stack behind a reverse proxy (nginx, Traefik, or a platform load balancer) that handles HTTPS and forwards traffic to the app service.
- **Session cookies**: Set `SESSION_COOKIE_SECURE=1` and `SESSION_COOKIE_SAMESITE=Strict` (or `Lax`) when served over HTTPS.
- **Scaling**: Adjust `GUNICORN_WORKERS` and `GUNICORN_THREADS` based on CPU and concurrent user expectations. For multi-host scaling, use an external Redis instance and a shared file store or object storage for archives.
- **Logging**: Gunicorn logs to stdout/stderr; aggregate logs via the orchestrator or forward to a log collector.
- **Monitoring**: Leverage `/healthz` for liveness/readiness probes. Add application metrics or structured logging as needed.
- **Secrets**: Inject sensitive values with your orchestrator’s secret manager rather than storing them in plain `.env` files.
- **Backups**: Ensure mounted volumes or their backing stores are backed up according to compliance requirements.
- **LLM/Speech**: Populate Azure OpenAI and Speech keys before enabling the Hey OMAR or Scribe features. Without keys, the app falls back to dev stubs.

## 6. Source changes supporting deployment

- Pinned dependency versions and introduced Gunicorn runtime (`requirements.txt`).
- Added `wsgi.py` and `gunicorn.conf.py` for production entrypoint configuration.
- Introduced `/healthz` endpoint for health checks.
- Added Dockerfile, `.dockerignore`, and docker-compose stack with Redis and persistent volumes.
- Provided environment template and documentation to ensure repeatable configuration.

## 7. Next steps

- Integrate CI to build and scan the container image, then push to a registry (e.g., GitHub Container Registry, ACR, ECR).
- Wire deployment automation (GitHub Actions, Azure DevOps, etc.) that consumes the same Dockerfile.
- Extend observability (structured logging, traces, additional metrics endpoints) as operational requirements evolve.
