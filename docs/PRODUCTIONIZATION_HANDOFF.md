# Lucent productionization handoff

Updated: 2026-09-07  
Branch: `feature/public-auth-flow`

This handoff tracks the phased move from the accepted RAG V1 implementation to an initial production-ready application. The validated RAG/Learn behavior in `docs/RAG_V1_IMPLEMENTATION_HANDOFF.md` remains an invariant.

## Phase status

### Phase 1 — Tier 1 production hardening: complete

- **Anthropic timeout/retry bounds:** the shared Anthropic client now defaults to a 20-second timeout and one retry. Existing narrower per-call policies, including no-retry tutor and section-note calls, remain authoritative. Both defaults are configurable with `ANTHROPIC_TIMEOUT_SECONDS` and `ANTHROPIC_MAX_RETRIES`, and invalid values fail startup.
- **Database pool hardening:** SQLAlchemy now enables `pool_pre_ping`, a five-connection steady pool, five overflow connections, a 15-second checkout timeout, and 30-minute connection recycling. These conservative defaults fit the current single API process and small initial PostgreSQL deployment. They are configurable with `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_POOL_TIMEOUT_SECONDS`, and `DATABASE_POOL_RECYCLE_SECONDS`; invalid values fail startup.
- **Bounded note/quiz prompts:** legacy document note and quiz generation now deterministically limit source text to 48,000 characters (approximately 12,000 input tokens), retaining 70% from the start and 30% from the end with an explicit omission marker. Both public generation paths use the same helper and oversized-source tests assert that the original unbounded value never reaches the provider.
- **Terminal progressive-ingestion failures:** the background job now catches pipeline/persistence/indexing failures, marks every unfinished section and the job failed, returns a safe user-facing error, and logs only the operation/job ID and exception class—not source content or exception text.
- **Bounded frontend polling:** both the production Notes page and ingestion inspector use one five-minute bounded poll loop with backoff from 500 ms to 3 seconds. Backend failure and client timeout become explicit terminal errors; cancellation exits without stale state updates.

The paid Voyage tier was already established before this phase and was not changed.

### Phase 2 — Tier 2 reliability hardening: complete

- **Safe provider-failure observability:** structured Anthropic generation, tutor diagnosis/decision/Ask, semantic section generation, Ask interaction validation, legacy learning-object fallback, and step-through runtime failures now log bounded operation/stage, exception class, and outcome fields. Prompt text, document/source content, learner responses, generated validation payloads, exception messages, and tracebacks are excluded from these failure logs. Existing retrieval and source-index lifecycle logging from `84cde27` remains the canonical RAG instrumentation and was not duplicated.
- **Bounded progressive-job lifecycle:** terminal in-memory ingestion jobs remain inspectable for 30 minutes by default and are then evicted. The store is capped at 200 entries by default; active jobs are never discarded, and new work receives a safe `503 ingestion_capacity_reached` response at capacity. Configure these bounds with `PROGRESSIVE_JOB_TTL_SECONDS` and `PROGRESSIVE_JOB_MAX_ENTRIES`; invalid values fail startup.
- **Duplicate authentication work removed:** cookie sessions and bearer users are cached only on the current request after their normal database validation/touch. A CSRF-protected write that resolves both `require_csrf` and `get_current_user` now performs one session query and one idle-expiry touch/commit. Revocation, status, idle/absolute expiry, origin, token hashing, cookie/header matching, and bearer validation are unchanged.
- **Paid-tier Voyage retry policy:** the default is now two retries after the initial request with a one-second fallback for rate limits, replacing the free-tier-oriented 20.5-second delay. Numeric and HTTP-date `Retry-After` values are honored and bounded to 60 seconds; explicit environment overrides remain supported.

The progressive job registry is intentionally still process-local. Polling therefore requires affinity to the API process that accepted the upload, and in-flight state is lost on a process restart. Moving this lifecycle to shared durable infrastructure is a future scaling concern, not part of this phase.

### Phase 3 — Basic production observability: complete

- **Request latency:** every HTTP response emits method, matched route template, status, outcome, exception class, and end-to-end duration. Query strings, request bodies, user/session IDs, and headers are excluded.
- **Anthropic operations:** structured provider calls emit one terminal event with the bounded operation/tool name, validation/request stage, outcome, exception class, latency, model/stop reason, token usage when returned, and output budget. The log never includes the prompt or generated payload.
- **Voyage operations:** document/query embedding calls emit one terminal event with operation, outcome, exception class, latency, attempt count, item count, and model. Input text and credentials are excluded. Numeric and HTTP-date retry hints continue to use the Phase 2 bounded policy.
- **RAG attribution:** the existing exact-retrieval telemetry continues to separate query-embedding, search, and total latency and records supported/weak/unavailable outcomes. Source indexing already records provider/model, embedded count, duration, and bounded failure codes.
- **Ingestion outcomes:** progressive jobs now emit terminal success/error duration and section count events without job, document, or source-content identifiers. Existing fallback events identify the bounded pipeline stage and exception class.
- **Operational log delivery:** `LOG_LEVEL` defaults to `INFO`, is startup-validated, and the `app` logger reuses Uvicorn's configured output stream. This makes successful latency events visible in the deployed process without introducing a telemetry platform dependency.

These stable event fields can be aggregated by the deployment log collector to calculate per-route/provider p50/p95 latency, provider error/fallback counts, retrieval contribution, and progressive-ingestion failure rates. Phase 3 intentionally adds measurement only; it does not optimize or replace any RAG/Learn path.

### Phase 4 — CI, reproducible deployment, and readiness: complete

- **Continuous integration:** `.github/workflows/ci.yml` runs on pull requests, `main` pushes, and manual dispatch. The backend job installs pinned Python dependencies, starts PostgreSQL 16, applies and verifies Alembic head, and runs the complete deterministic suite with tutor-model calls disabled. The frontend job installs from `package-lock.json`, typechecks, runs the complete suite, and builds production assets. No provider credentials or live calls are required.
- **Backend image:** `backend/Dockerfile` builds the existing FastAPI monolith on pinned Python 3.13 and starts the explicit Uvicorn production command as a non-root user. Migrations are present in the image but run as a separate release step.
- **Frontend image:** `web/Dockerfile` builds with pinned Node 22 and serves immutable assets plus SPA fallback through pinned Nginx. `VITE_API_URL` is an explicit build argument and the static server has its own lightweight liveness endpoint.
- **Reference deployment:** `compose.production.yml` describes only the current architecture—PostgreSQL, a one-shot migration container, one API process, and one static web process—with health-gated startup. It intentionally keeps one API replica because progressive jobs are process-local.
- **Configuration/runbook:** `.env.production.example` enumerates required security, provider, pool, retry, logging, upload, and lifecycle settings. `docs/PRODUCTION_DEPLOYMENT.md` documents build/migrate/start, OAuth/origin constraints, probes, release verification, rollback boundaries, and the external provider privacy gate.
- **Liveness/readiness:** `/healthz` proves process liveness without dependencies. `/readyz` executes a PostgreSQL probe and requires the database's Alembic revision set to exactly match the repository heads. Failure returns a bounded 503 reason without connection details. Readiness deliberately avoids Anthropic/Voyage calls.

### Phase 5 — final production acceptance and regression: complete

- **Technical status:** Lucent is ready for an initial controlled production/beta deployment using the documented single-API topology. The complete deterministic backend/frontend gates, PostgreSQL migration gate, live readiness probes, and representative authorized-CC0 browser journeys pass.
- **RAG/Learn preservation:** no learner-runtime functionality changed during Phase 5. Fresh Pendulum and Satire ingestion reconfirmed source-backed notes and ready indexes. A fresh Pendulum Learn session reconfirmed cohesive grounded teaching, wrong-answer teaching before retest, Ask-selected visual replacement, and exact scene/interaction/visual persistence after refresh.
- **Prerequisite acceptance:** the previously completed fresh browser journey remains the accepted end-to-end proof: a genuine dependent Satire objective branched to its source-backed prerequisite, taught and assessed the prerequisite, survived an exact refresh, returned to the parent objective after sufficient evidence, and then recorded correct parent application evidence. Phase 1–4 did not modify Learn pedagogy or persistence, and the final Learn/runtime regression suite remained green.
- **Golden coverage:** the accepted two-domain Pendulum and Satire journeys remain the complete evidence for uncertainty support, scaffold fading, independent application, transfer, delayed review, evidence-based completion, grounded Ask behavior, visual persistence, and refresh/resume. Phase 5 added fresh post-production ingestion and Learn smoke evidence rather than manufacturing a prerequisite branch where the newly generated source plan had no genuine prerequisite dependency.
- **Repository hygiene:** all pre-existing user-owned deleted/untracked files remain untouched. No temporary browser evidence or generated acceptance fixture was staged.

## Validation evidence

- Focused backend hardening/ingestion/note/quiz suite: 65 passed.
- Frontend progressive polling tests: 4 passed.
- Full frontend suite: 128 passed.
- Production frontend build: passed (existing large-chunk warning remains).
- Browser smoke using only the checked-in CC0 Pendulum fixture:
  - uploaded through the real progressive PDF UI;
  - visibly entered the `Building notes…` processing state;
  - completed and navigated to fresh material `16` with generated notes;
  - started a fresh source-grounded Learn session;
  - submitted the grounded correct interaction and observed feedback plus the next authoritative scene/Continue state.
- Full backend suite: 411 passed, 7 existing warnings.

### Phase 2 validation evidence

- Focused provider/auth/job-lifecycle/RAG/Learn suite: passed.
- Full backend suite: 419 passed, 7 existing dependency deprecation warnings.
- Full frontend suite: 128 passed.
- Production frontend build: passed (the existing large-chunk warning remains).
- PostgreSQL migration state: `0010_persist_learning_blocks (head)` for both current revision and repository head.
- Updated backend restarted successfully; `GET http://127.0.0.1:8000/docs` returned HTTP 200.
- The authenticated write contract remains covered end-to-end by the security/API suite, including valid CSRF acceptance, invalid/missing CSRF rejection, and the new assertion that cookie-session resolution/touch occurs only once per request.
- Native browser smoke could not be repeated at this checkpoint because the local Mac was locked and the browser-control surface could not unlock it. No product/browser failure was observed; the Phase 1 CC0 browser evidence above remains the latest interactive smoke.

### Phase 3 validation evidence

- Focused telemetry/provider/auth/RAG/Learn tests: passed, including assertions that request queries, embedding input, prompts, provider exception text, and learner/source content do not enter telemetry.
- Full backend suite: 421 passed, 7 existing dependency deprecation warnings.
- Full frontend suite: 128 passed.
- Production frontend build: passed (the existing large-chunk warning remains).
- Running backend health: HTTP 200, with the emitted event `http_request_complete method=GET route=/ status=200 outcome=success ... duration_ms=0.6` observed in the Uvicorn stream.
- Native interactive browser smoke remains unavailable because the Mac is locked. This is an environment restriction rather than an observed application failure; no user-facing code changed in this phase.

### Phase 4 validation evidence

- Focused readiness and preserved production-hardening tests: 15 passed.
- Full backend suite: 425 passed, 7 existing dependency deprecation warnings.
- Frontend typecheck: passed.
- Full frontend suite: 128 passed.
- Production frontend build: passed (the existing large-chunk warning remains).
- CI and Compose YAML parsed successfully; `docker compose config --quiet` accepted the production configuration with the checked-in example values.
- Live local backend returned HTTP 200 from both `/healthz` and `/readyz` against PostgreSQL at migration head.
- Alembic current and repository heads both report `0010_persist_learning_blocks (head)`.
- Docker CLI is installed, but local image builds could not run because Docker Desktop's daemon was unavailable while the Mac remained locked. The exact build definitions and resolved Compose graph were validated; Phase 5 retained the image smoke as a documented release-environment gate after confirming the daemon remained externally unavailable.

### Phase 5 final validation evidence

- Complete backend suite: **425 passed**, with 7 existing dependency deprecation warnings.
- Frontend typecheck: passed.
- Complete frontend suite: **128 passed**.
- Production frontend build: passed; the existing large-chunk warning remains non-blocking.
- Python application/script compilation: passed.
- PostgreSQL migration state: current and repository heads both report `0010_persist_learning_blocks (head)`.
- CI and Compose YAML parsing: passed. `docker compose config --quiet` passed using `.env.production.example` as the explicit validation input.
- Live service probes: `/healthz` and `/readyz` both returned HTTP 200; the frontend returned HTTP 200.
- Fresh authorized-CC0 browser ingestion:
  - Pendulum document `13`, generation `02e77b65-1a43-4e33-b1eb-b634f012140e`, reached `READY` and rendered substantive pendulum notes.
  - Satire document `14`, generation `41607811-d2f3-4ad3-b976-dceb9469dcf6`, reached `READY` and rendered substantive satire notes.
- Fresh Pendulum Learn browser smoke: session `9d3ff62b-04a3-4180-b9aa-535e3231971f` visibly rendered an explanation, the `Position, Energy, and Force Around One Swing` visual, and active grounded ordering practice. An intentional wrong response advanced revision 1 to 2, produced misconception-specific teaching before a new visual-linked repair interaction, and did not resurrect the answered interaction. Ask `Show me visually` advanced revision 2 to 3, replaced the main visual with `Relationship view: Position, Energy, and Force Around One Swing`, preserved the active interaction intentionally, and the exact revision, interaction, and visual survived reload.
- Accepted prerequisite browser evidence: `.tmp/learn-golden/rag-v1/prerequisite-final/01-foundation.png` through `08-original-objective-success.png`, with machine-readable assertions in `journey-result.json`.
- Accepted complete two-domain evidence: `.tmp/learn-golden/rag-v1/pendulum/` and `.tmp/learn-golden/rag-v1/satire/`; final post-cleanup smoke is under `.tmp/learn-golden/rag-v1/pendulum-final-post-cleanup/`, and the fresh Phase 5 smoke is under `.tmp/learn-golden/rag-v1/production-phase5-pendulum/`.
- Runtime telemetry was observed for authenticated browser requests, Anthropic section generation, Voyage document embedding, source-index readiness, and readiness checks. Logged fields contained bounded operation metadata and timings, not source text or prompts.
- `git diff --check`: passed for intended tracked work.
- Docker image execution could not be performed locally because the installed Docker Desktop daemon remained unavailable. The Dockerfiles, resolved Compose graph, migration ordering, health gates, and static-server configuration were validated. This is an environment limitation, not an observed image-definition failure; the first deployment/CI image build should perform the documented image smoke.

## Production audit disposition

The read-only audit was located later in the preserved local `.tmp/audit/` workspace and reviewed during Phase 5. It was not staged because `.tmp/` is pre-existing user-owned workspace state.

| Finding | Disposition | Rationale |
| --- | --- | --- |
| S1-a — no deployment configuration | **FIXED** | Pinned backend/frontend images, production Compose topology, explicit environment template, and deployment/rollback runbook were added in Phase 4. |
| S1-b — CI does not validate the app | **FIXED** | PR/main/manual CI now applies migrations and runs the complete backend suite plus frontend typecheck, suite, and production build. |
| S1-c — unbounded Anthropic timeouts | **FIXED** | The shared client has bounded configurable timeout/retry defaults; deliberately narrower learner-path overrides remain intact. |
| S1-d — default DB pool/no pre-ping | **FIXED** | The engine uses startup-validated bounded pool settings, pre-ping, checkout timeout, and recycling. |
| S1-e — failed ingestion and runaway polling | **FIXED** | Jobs terminate safely on failures and both clients use bounded backoff polling with explicit failure/timeout states. |
| S1-f — unbounded document prompts | **FIXED** | Note and quiz prompts use the shared deterministic 48,000-character source budget. |
| S2-a — quiz retrieval fan-out | **DEFERRED WITH RATIONALE** | Correctness and grounding are intact, and the paid Voyage tier removes the audit's free-tier 61.5-second throttle pathology. Batching would change retrieval plumbing and was outside the no-new-functionality final checkpoint. Measure quiz creation latency in production telemetry and batch only if it is material. |
| S2-b — silent provider failures | **FIXED** | Bounded structured fallback/failure events now cover Anthropic, Voyage, Learn, Ask, retrieval, indexing, ingestion, and step-through paths without sensitive content. |
| S2-c — unbounded/process-local progressive jobs | **MITIGATED** | TTL and capacity bounds prevent unbounded retention. The documented initial deployment intentionally uses one API replica, preserving polling affinity; durable multi-replica jobs remain a future scaling item. |
| S2-d — duplicate auth session work | **FIXED** | Normal validation/touch is cached on the request, preserving CSRF and expiry semantics while eliminating duplicate reads/commits. |
| S2-e — no readiness probe | **FIXED** | `/readyz` validates PostgreSQL connectivity and exact Alembic head; `/healthz` provides dependency-free liveness. |
| S3-a — JSONB embedding storage | **DEFERRED WITH RATIONALE** | Measured internal retrieval cost is negligible at the current corpus scale. No pgvector/vector DB work is justified for the initial release. |
| S3-b — retrieval loads full entities | **DEFERRED WITH RATIONALE** | Current measured latency is negligible. Revisit only with production evidence at materially larger document sizes. |
| S3-c — large `ask_lucent` route | **DEFERRED WITH RATIONALE** | This is maintainability debt in a heavily validated path, not a release correctness issue; broad refactoring was explicitly prohibited before release. |
| S3-d — repository hygiene | **DEFERRED WITH RATIONALE** | The listed deleted/untracked files predate productionization and belong to the user. They were preserved rather than destructively cleaned. |

The audit's security/ownership, async ingestion, batch indexing, and production configuration checks remain **NO LONGER APPLICABLE AS FINDINGS / VERIFIED SOUND**; no contrary regression was found.

## Technical limitations and launch gates

### Known technical limitations

- Progressive ingestion state remains process-local. The initial production topology must stay at one API replica (or use sticky affinity); durable shared jobs are required before horizontal API scaling.
- Ask Lucent intentionally performs two distinct sequential Anthropic operations. Production telemetry should determine whether this learner-visible latency merits later consolidation.
- Quiz source association currently performs per-question retrieval. Paid-tier retry tuning makes it functionally acceptable for initial beta, but telemetry should determine whether batching is warranted.
- Embeddings remain JSONB and exact retrieval loads full persisted block entities. Both are measured as negligible at present scale and should be revisited only with evidence.
- The production frontend build emits a large-chunk warning. It does not affect correctness; targeted code splitting can be considered after launch metrics identify a user impact.
- Docker Desktop was unavailable for a local image-run smoke. Run the documented image build/migrate/readiness smoke in the actual release environment before exposing traffic.

### External, privacy, legal, and operator launch gates

- Confirm Anthropic and Voyage processing, retention, regional, and contractual terms for real student documents. Only checked-in authorized/CC0 fixtures were sent during development acceptance.
- Provision production Anthropic and paid Voyage credentials through the deployment secret store; do not copy development credentials into images or source control.
- Configure the final HTTPS web/API origins, strong application secrets, production Google OAuth redirect URI/client credentials, and the exact CORS/CSRF allowlists.
- Provision and back up the managed PostgreSQL database, run the migration release step, build/run both images, and verify `/healthz`, `/readyz`, sign-in, upload, Learn, and rollback procedures on the chosen host.
- Enable a production log collector/alert policy over the structured events added in Phase 3 and establish an operator for provider/fallback, ingestion-failure, readiness, and latency alerts.

## Preserved unrelated workspace state

The pre-existing deleted cohesive-tutor plan, its untracked `_OLD` copy, `.tmp/`, and `backend/:memory:.ses` were not modified or staged.

## Final checkpoint

Phases 1–5 are complete. The next action is operational release preparation: satisfy the external/privacy gates above, run the documented image smoke on a host with a working Docker daemon, and deploy the accepted single-API topology. No further productionization feature work is part of this master goal.
