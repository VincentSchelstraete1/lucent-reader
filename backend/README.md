# Lucent backend

The API uses PostgreSQL and Alembic for schema changes.

From `backend/`, apply migrations with:

```bash
venv/bin/alembic upgrade head
```

For an existing development database created before Alembic, mark the existing
base schema and then apply the passage-column migration without recreating data:

```bash
venv/bin/alembic stamp 0001_initial_schema
venv/bin/alembic upgrade head
```

Use `venv/bin/alembic current` to inspect the installed revision. New empty
databases should run only `upgrade head`.
# Authentication configuration

Production requires `APP_ENV=production`, `DATABASE_URL`, `API_ORIGIN`, an
explicit comma-separated `ALLOWED_ORIGINS`, `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `COOKIE_SECURE=true`, and the
comma-separated Chrome extension IDs in `LUCENT_EXTENSION_IDS`. The Google
redirect URI must exactly match `/auth/google/callback` on the public API
origin. Production startup fails closed when its required settings are absent
or development-only switches are enabled.

The web app uses an opaque server-side session in an HttpOnly cookie. The
extension uses an independent device grant with a 15-minute opaque access
token and a rotating opaque refresh token; the refresh token is persisted only
in `chrome.storage.local`, while access tokens use `chrome.storage.session`.

## One-time local legacy ownership claim

The development database predates user ownership. This repository deliberately
does not guess an owner. Apply the staging migration, enable the claim for one
verified Google login, then enforce ownership:

1. `alembic upgrade 0003_auth_ownership`
2. Set `APP_ENV=development` and `ENABLE_LEGACY_CLAIM=true`, configure Google,
   then complete one real Google login through FastAPI.
3. Confirm `legacy_claims` contains exactly one row and no Source has a null
   `user_id`.
4. Remove or set `ENABLE_LEGACY_CLAIM=false` immediately.
5. `alembic upgrade head`

The claim only selects currently unowned Sources, runs while holding row locks,
and records a singleton completion row. Rerunning it for the same verified user
is a no-op; a different user receives a conflict. It is rejected by production
configuration. Documents, Notes, and Quizzes retain ownership through their
existing Source relationships; QuizAttempts are backfilled from that same
graph before their direct `user_id` becomes non-null.

`ENABLE_DEVELOPMENT_AUTH=true` optionally exposes the deterministic backend
development user, but only with `APP_ENV=development`. It never performs or
claims to perform Google login and cannot claim legacy data.
