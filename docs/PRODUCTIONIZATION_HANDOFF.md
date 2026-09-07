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

## Audit/source note

`AUDIT_REPORT.md` was not present in the repository, any branch history, or the supplied attachment directory at this checkpoint. Phase 1 was therefore reconciled against the explicit Tier 1 findings in the user-provided productionization objective and the current code/history. No absent-audit claim was treated as additional scope.

## Preserved unrelated workspace state

The pre-existing deleted cohesive-tutor plan, its untracked `_OLD` copy, `.tmp/`, and `backend/:memory:.ses` were not modified or staged.

## Next phase (do not begin without explicit instruction)

Phase 3 is the next productionization phase. Begin only after explicit instruction, preserving the Phase 1/2 reliability boundaries and the accepted RAG/Learn behavior.
