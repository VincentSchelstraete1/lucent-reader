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

## Audit/source note

`AUDIT_REPORT.md` was not present in the repository, any branch history, or the supplied attachment directory at this checkpoint. Phase 1 was therefore reconciled against the explicit Tier 1 findings in the user-provided productionization objective and the current code/history. No absent-audit claim was treated as additional scope.

## Preserved unrelated workspace state

The pre-existing deleted cohesive-tutor plan, its untracked `_OLD` copy, `.tmp/`, and `backend/:memory:.ses` were not modified or staged.

## Next phase (do not begin without explicit instruction)

Phase 2 covers the scoped Tier 2 reliability work: safe provider-failure observability, bounded lifecycle cleanup for in-memory progressive jobs, duplicate auth-session work where it can be fixed without weakening security, and paid-tier Voyage retry tuning. It must preserve this phase and the accepted RAG/Learn browser behavior.
