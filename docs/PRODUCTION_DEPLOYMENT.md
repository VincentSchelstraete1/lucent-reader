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
web origin and approved `chrome-extension://...` origins. `LUCENT_EXTENSION_IDS`
contains the corresponding bare 32-character Chrome IDs, not URLs. The Google
console redirect URI must exactly equal `GOOGLE_REDIRECT_URI`.
The Vite production build also fails unless `VITE_API_URL` (provided from
`PUBLIC_API_ORIGIN` in Compose) is a plain HTTPS origin.

Provider inputs can contain authorized uploaded material. Production use with
real student documents remains gated on the separate privacy/legal review of
Anthropic and Voyage processing and retention terms.

The application uses server-generated opaque session credentials and stores
only their hashes, so there is no static session-signing secret. Treat the
Google client secret, Anthropic and Voyage keys, PostgreSQL password, and any
hosting credentials as strong application secrets: generate independent
high-entropy values, store them in the hosting provider's secret manager,
restrict operator access, and rotate them after suspected exposure. Never put
production values in an image, Compose file, frontend build argument, or Git.

### Origins and Google OAuth

- `PUBLIC_API_ORIGIN` and `API_ORIGIN` are the exact public HTTPS API origin,
  with no path and no trailing slash.
- Put the exact HTTPS web origin first in `ALLOWED_ORIGINS`; list only the
  production web origin and explicitly approved Chrome extension origins.
- Register exactly `${API_ORIGIN}/auth/google/callback` in the production
  Google OAuth client and set that same value as `GOOGLE_REDIRECT_URI`.
- Keep `COOKIE_SECURE=true`, `ENABLE_DEVELOPMENT_AUTH=false`, and
  `ENABLE_LEGACY_CLAIM=false`. Production startup rejects unsafe auth values.
- Set `SUPPORT_EMAIL` and `POLICY_EFFECTIVE_DATE` before building the frontend;
  these values are compiled into the public Privacy and Terms pages.

### Provider-spend safeguards

The single API process enforces atomic per-user and process-global windows for
document ingestion and provider-backed generation. Ask Lucent also retains its
database-backed per-user request check. Ingestion is rejected before its first
provider request when normalized source characters or estimated provider
fan-out exceed configured limits. The estimate includes representation
classifier fallbacks, section generation, Voyage embedding batches, and
configured retries.

All thresholds in `.env.production.example` are conservative starting points,
not product entitlements. Compare them with the active Anthropic/Voyage tier
before launch and lower them if necessary. Process counters reset on API
restart, so configure provider-account budgets and billing alerts as the
durable, account-wide backstop. Do not add another API replica: these counters
and progressive ingestion intentionally rely on the documented single-process
topology.

## Build, migrate, and start

### Render Blueprint

The repository-root `render.yaml` prepares the intended public topology:

- exactly one paid API instance at `api.lucentreader.com`;
- one static frontend at `lucentreader.com`;
- one private-network-only paid PostgreSQL 16 database;
- `alembic upgrade head` as the API pre-deploy command; and
- `/readyz` as Render's traffic health check.

Create a Render Blueprint from this repository and branch. Before its first
deploy, supply every `sync: false` value in the dashboard. Set
`ALLOWED_ORIGINS` to
`https://lucentreader.com,chrome-extension://<production-extension-id>` and set
`LUCENT_EXTENSION_IDS` to the same bare extension ID. Render supplies
`DATABASE_URL`; the backend safely selects the installed Psycopg 3 driver for
Render's standard `postgresql://` connection string.

The Blueprint uses one API instance intentionally. Do not enable autoscaling or
increase `numInstances` without first replacing the documented process-local
ingestion jobs and global cost limiters.

After the Blueprint deploys, verify both `GET /healthz` and `GET /readyz`
return 200 and open the frontend root and `/app`. Render monitors `/readyz`;
`/healthz` remains the independent liveness check used during diagnosis.

### Portable Docker deployment

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
6. Exercise a configured usage limit and verify the API returns HTTP 429 with
   `usage_limit_reached` and `Retry-After`, and that the UI shows the safe
   temporary-limit message.

Rollback the application image independently of the database. Database rollback
requires an explicitly reviewed Alembic downgrade; never discard the PostgreSQL
volume or run a destructive reset as part of an application rollback.

## Database backup and restore readiness

Use a managed PostgreSQL service with encrypted storage, automated daily
backups, and point-in-time recovery. For the initial public release, retain at
least seven days of recovery history, assign an operator to review backup
failures, and test a restore into an isolated database before sending traffic.
These are infrastructure actions; checking in this runbook does not prove that
the production database has been backed up.

For a portable logical backup, run `pg_dump --format=custom --no-owner` against
the managed database and write the result directly to encrypted operator-owned
storage. Never commit a dump. To verify recovery, create an isolated empty
database, restore with `pg_restore --clean --if-exists --no-owner`, run
`alembic current`, and exercise `/readyz`, authentication, an authorized upload,
Learn, and Ask Lucent against the restored instance. Destroy the isolated copy
only after recording the outcome. Follow the managed provider's native
point-in-time restore procedure for incident recovery rather than overwriting
the affected production database in place.

## Logging and alert ownership

Send stdout/stderr to a production log collector with access controls and a
documented retention period. Assign one named operator before launch. Alert on
repeated readiness failures, `ingestion_job_complete outcome=error`, source
index terminal failures, sustained provider errors/fallbacks, and global usage
limits. Dashboards and alerts must use the structured metadata fields and must
not capture request bodies, uploaded text, learner responses, prompts, provider
payloads, cookies, authorization headers, or query strings.

## External launch gates

Before accepting real student documents, the service owner must:

1. approve the final Privacy notice and Terms with appropriate legal advice;
2. confirm Anthropic and Voyage processing, retention, region, and contractual
   terms for the intended users and content;
3. decide and publish application, log, and backup retention periods plus the
   account deletion/export support process;
4. verify the production support address is monitored;
5. configure provider budgets/alerts and name the operator who receives them;
6. record a successful managed-database backup and isolated restore drill.

Until these actions are recorded, the code may be deployment-ready but the
service is not approved for unrestricted public document ingestion.

## Chrome extension release

The extension reads `PLASMO_PUBLIC_API_URL` and
`PLASMO_PUBLIC_WEB_APP_URL` at build time. `npm run dev` retains the local
defaults `http://127.0.0.1:8000` and `http://localhost:5173`.

From the repository root:

```bash
corepack enable
pnpm install --frozen-lockfile
pnpm test
pnpm build
pnpm package
```

The release commands default to `https://api.lucentreader.com` and
`https://lucentreader.com`. They reject HTTP, credentials, paths, query
strings, fragments, and any origin not explicitly present in the checked-in
manifest host permissions. An alternate authorized domain can be supplied at
build time, but its exact `https://.../*` permission must be reviewed and
checked in first:

```bash
PLASMO_PUBLIC_API_URL=https://api.example.com \
PLASMO_PUBLIC_WEB_APP_URL=https://app.example.com \
pnpm package
```

The packaged archive is written under `build/`. Inspect its generated manifest
and upload that archive through the Chrome Web Store publisher account; creating
the archive does not publish it.
