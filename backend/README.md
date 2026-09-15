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
or development-only switches are enabled. Extension IDs are bare 32-character
Chrome IDs; their matching `chrome-extension://<id>` origins must also appear
in `ALLOWED_ORIGINS`.

The web app uses an opaque server-side session in an HttpOnly cookie. The
extension uses an independent device grant with a 15-minute opaque access
token and a rotating opaque refresh token; the refresh token is persisted only
in background-origin IndexedDB (not extension storage exposed to content
scripts), while access tokens use `chrome.storage.session`.

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

## PDF ingestion inspector

Install dependencies from `requirements.txt`, then optionally configure the
maximum in-memory PDF upload size in bytes (the default is 20 MiB):

```bash
PDF_UPLOAD_MAX_BYTES=20971520
```

Authenticated web clients can send a multipart request with a `file` field to
`POST /ingestion/pdf`. The endpoint validates and converts the PDF in memory.
PyMuPDF preserves physical pages, raw layout blocks, bounding boxes, and inline
image assets; MarkItDown independently supplies its raw global `text_content`.
Both representations are returned in one non-normalized `RawDocument`, and no
Source or Document rows are created. Inline image data is temporary response
data rather than durable storage. The web development server exposes the inspector at
`/app/dev/ingestion`; the route is omitted from production web builds.

The response also includes a deterministic `NormalizedDocument` beside the raw
representation. It suppresses only conservatively detected repeated page
furniture, repairs narrow layout artifacts, retains RawBlock/Image provenance,
and records every transformation or unresolved suspicious artifact. It does not
perform semantic segmentation. To print a task-specific evaluation report for
one or more local PDFs without persistence, run from `backend/`:

```bash
PYTHONPATH=. venv/bin/python scripts/evaluate_normalization.py /path/to/file.pdf
```

## RAG source indexing

Learn and Ask Lucent use persisted original-source `LearningBlock` records.
Configure the server without checking secrets into the repository:

```bash
VOYAGE_API_KEY=your-server-side-key
RAG_EMBEDDING_MODEL=voyage-3-lite
RAG_EMBEDDING_DIMENSIONS=512
RAG_EMBEDDING_TIMEOUT_SECONDS=20
RAG_EMBEDDING_BATCH_SIZE=32
```

New PDF, DOCX, and PPTX ingestion persists the source corpus before note
generation and indexes it asynchronously. Check safe public readiness at
`GET /documents/{document_id}/source-index`. Legacy documents without an index
must be re-uploaded; generated notes are never used as retrieval evidence.

After a local process restart, retry PENDING, FAILED, or expired indexing
leases from `backend/` with:

```bash
PYTHONPATH=. venv/bin/python scripts/index_learning_blocks.py
```

The command reuses persisted source blocks and does not require original upload
files. Provider failures are stored as bounded failure codes; raw source,
queries, vectors, and provider errors are not written to ordinary logs.
