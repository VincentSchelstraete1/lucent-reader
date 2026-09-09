# Lucent initial production deployment

Lucent's initial production shape is deliberately small: one FastAPI process,
one statically served React build, and PostgreSQL. Progressive ingestion jobs
remain in the API process, so deploy exactly one API replica for this release.

## Required configuration

Copy `.env.production.example` to an untracked `.env.production` and replace
every placeholder. Never commit that file. `APP_ENV=production` fails closed
unless Google OAuth, HTTPS API origin, secure cookies, and production-safe auth
switches are configured.

`PUBLIC_API_ORIGIN` is baked into the frontend at build time. It must equal the
public HTTPS API origin. `ALLOWED_ORIGINS` is the comma-separated list of the
web origin and any approved extension origins. The Google console redirect URI
must exactly equal `GOOGLE_REDIRECT_URI`.

Provider inputs can contain authorized uploaded material. Production use with
real student documents remains gated on the separate privacy/legal review of
Anthropic and Voyage processing and retention terms.

## Build, migrate, and start

The checked-in Compose file is a reproducible reference deployment:

```bash
cp .env.production.example .env.production
# edit .env.production with secret-manager supplied values
docker compose --env-file .env.production -f compose.production.yml build
docker compose --env-file .env.production -f compose.production.yml up -d
```

Do not run multiple copies of the `migrate` service concurrently. On a managed
platform, use the same backend image and run `alembic upgrade head` as a release
command before starting `uvicorn app.main:app --host 0.0.0.0 --port 8000
--proxy-headers --forwarded-allow-ips=*`.

## Health and readiness

- `GET /healthz` is liveness: it proves only that the API process can respond.
- `GET /readyz` is readiness: it opens a PostgreSQL connection and requires the
  database's Alembic revision set to exactly match the checked-in migration
  heads. It returns 503 without database details when either check fails.
- The frontend container exposes `GET /healthz` on port 8080.

Readiness deliberately does not call Anthropic or Voyage. Temporary provider
failure is handled by bounded requests and deterministic fallbacks rather than
removing the entire API from service.

## Release verification

Before directing traffic:

1. Run `alembic upgrade head` and confirm `alembic current` equals `alembic heads`.
2. Start the API and require `/healthz` and `/readyz` to return HTTP 200.
3. Start the web build and verify its `/healthz` endpoint.
4. Complete one authenticated CC0 ingestion and grounded Learn/Ask smoke test.
5. Inspect logs for bounded `http_request_complete`,
   `provider_operation_complete`, `retrieval_complete`, and
   `ingestion_job_complete` events.

Rollback the application image independently of the database. Database rollback
requires an explicitly reviewed Alembic downgrade; never discard the PostgreSQL
volume or run a destructive reset as part of an application rollback.
